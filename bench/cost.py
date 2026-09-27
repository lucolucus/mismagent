#!/usr/bin/env python3
"""Token cost of a build run, measured from Claude Code transcripts.

Zero-cost and deterministic: stdlib only, no LLM, no network; it only reads the transcripts and the
manifests. Without `--prices` it reports tokens only — it never invents a price.

    python3 bench/cost.py ~/.claude/projects/<escaped-project-path> [--session ID]... \
        [--manifest building-blocks.yaml]... [--feature-dir F]... [--prices prices.json] [--md]

Layout read: `<dir>/<session>.jsonl` (the orchestrating session) and
`<dir>/<session>/subagents/agent-<id>.jsonl` + `agent-<id>.meta.json` (one per dispatch). Each API
call is counted once by `message.id` across all files (forks replay their parent's history).
"""
import argparse
import glob
import json
import os
import re
import sys
from statistics import median

CLASSES = ("input", "cache_write", "cache_read", "output")
USAGE_KEYS = {"input": "input_tokens", "cache_write": "cache_creation_input_tokens",
              "cache_read": "cache_read_input_tokens", "output": "output_tokens"}
UNATTRIBUTED = "(unattributed)"
MAIN = "main"
CODE_REVIEW = "code-review"
CODE_REVIEW_SKILL = re.compile(r"\bskill\W{0,3}(?:[\w-]+:)?code-review\b", re.I)
CHECKPOINT_PROMPT = re.compile(r"^#{2,}\s*Checkpoint\b", re.I | re.M)
CHECKPOINT_RESULT = "RESULT: CHECKPOINT"


def na(reason):
    return {"n/a": reason}


def is_worker(kind):
    return kind.split(":")[-1].endswith("worker")


# ---- usage ---------------------------------------------------------------------------------------
class Usage:
    """Tokens per class, kept per model so a cost can be priced per model family."""

    def __init__(self):
        self.by_model = {}

    def add_call(self, model, usage):
        row = self.by_model.setdefault(model or "?", dict.fromkeys(CLASSES, 0))
        for c in CLASSES:
            row[c] += int(usage.get(USAGE_KEYS[c]) or 0)

    def merge(self, other):
        for model, row in other.by_model.items():
            mine = self.by_model.setdefault(model, dict.fromkeys(CLASSES, 0))
            for c in CLASSES:
                mine[c] += row[c]
        return self

    def tokens(self):
        t = dict.fromkeys(CLASSES, 0)
        for row in self.by_model.values():
            for c in CLASSES:
                t[c] += row[c]
        t["total"] = sum(t[c] for c in CLASSES)
        return t

    def cost(self, prices):
        """USD, or n/a when a model with tokens has no price or lacks the rate of a class it used
        (never a partial sum, never a silent zero)."""
        total = 0.0
        for model, row in sorted(self.by_model.items()):
            if not any(row.values()):
                continue
            p = price_for(model, prices)
            if p is None:
                return na("no price for model %s" % model)
            missing = [c for c in CLASSES if row[c] and not isinstance(p.get(c), (int, float))]
            if missing:
                return na("no %s rate for model %s" % ("/".join(missing), model))
            total += sum(row[c] * p[c] for c in CLASSES if row[c]) / 1e6
        return round(total, 4)


def load_prices(obj):
    """Validate a prices map: every entry has the four rates, as non-negative numbers."""
    if not isinstance(obj, dict) or not obj:
        raise ValueError("prices: expected a non-empty JSON object {model-family: {rates}}")
    for key, rates in obj.items():
        if not isinstance(rates, dict):
            raise ValueError("prices[%s]: expected an object of rates" % key)
        for c in CLASSES:
            v = rates.get(c)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ValueError("prices[%s].%s: missing or not a non-negative number (USD per Mtok)" % (key, c))
    return obj


def price_for(model, prices):
    """The longest price key contained in the model id (a family like `opus`, or a full id)."""
    keys = [k for k in prices if k.lower() in model.lower()]
    return prices[max(keys, key=len)] if keys else None


def summarize(usage, prices, calls=None):
    out = {"tokens": usage.tokens()}
    if calls is not None:
        out["calls"] = calls
    if prices is not None:
        out["cost_usd"] = usage.cost(prices)
    return out


# ---- transcripts ---------------------------------------------------------------------------------
def load_lines(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
    return ""


def read_file(path):
    """One transcript file → prompt, result text, and its calls: [(message id, model, usage)] in order.

    A message id may repeat (streamed lines): the per-class maximum is kept, i.e. the final usage."""
    lines = load_lines(path)
    prompt = ""
    for o in lines:
        if o.get("type") == "user" and not o.get("isMeta"):
            prompt = text_of((o.get("message") or {}).get("content"))
            break
    calls, result, last_text = {}, [], ""
    for o in lines:
        if o.get("type") != "assistant":
            continue
        m = o.get("message") or {}
        content = m.get("content")
        if isinstance(content, list):
            for x in content:
                if isinstance(x, dict) and x.get("type") == "tool_use" and x.get("name") == "SubagentHandback":
                    result.append(str((x.get("input") or {}).get("message", "")))
            t = text_of(content)
            if t:
                last_text = t
        mid, u = m.get("id"), m.get("usage")
        if mid and isinstance(u, dict):
            prev = calls.get(mid)
            calls[mid] = (m.get("model") or (prev and prev[0]),
                          max_usage(prev[1] if prev else {}, u))
    result.append(last_text)
    return {"prompt": prompt, "result": "\n".join(result), "calls": calls}


def max_usage(a, b):
    return {k: max(int(a.get(k) or 0), int(b.get(k) or 0)) for k in USAGE_KEYS.values()}


def read_meta(jsonl):
    path = jsonl[: -len(".jsonl")] + ".meta.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def kind_of(meta, prompt):
    if CODE_REVIEW_SKILL.search(prompt):
        return CODE_REVIEW
    return meta.get("agentType") or "?"


def account(s, owner, best, me):
    """Usage, turns and final context of the calls this file originated."""
    usage, turns, last_ctx = Usage(), 0, 0
    for mid in s["calls"]:
        if owner[mid] != me:
            continue
        model, u = best[mid]
        usage.add_call(model, u)
        turns += 1
        last_ctx = sum(int(u.get(USAGE_KEYS[c]) or 0) for c in ("input", "cache_write", "cache_read"))
    s.update(usage=usage, turns=turns, final_context=last_ctx)
    return s


def collect(tdir, sessions=None):
    """Main sessions and dispatches. Each message id counts once: its final usage, attributed to the
    first file (in an order where a parent precedes its forks, which replay its history)."""
    wanted = set(sessions) if sessions else None
    mains = sorted(p for p in glob.glob(os.path.join(tdir, "*.jsonl"))
                   if wanted is None or os.path.basename(p)[:-6] in wanted)
    subs = sorted(p for p in glob.glob(os.path.join(tdir, "*", "subagents", "agent-*.jsonl"))
                  if wanted is None or os.path.basename(os.path.dirname(os.path.dirname(p))) in wanted)
    metas = {p: read_meta(p) for p in subs}
    subs.sort(key=lambda p: (bool(metas[p].get("isFork")), int(metas[p].get("spawnDepth") or 1), p))
    files = [(p, read_file(p)) for p in mains + subs]
    owner, best = {}, {}
    for p, s in files:
        for mid, (model, u) in s["calls"].items():
            owner.setdefault(mid, p)
            prev = best.get(mid)
            best[mid] = (model or (prev and prev[0]), max_usage(prev[1] if prev else {}, u))
    main_usage, main_calls, dispatches = Usage(), 0, []
    for p, s in files:
        account(s, owner, best, p)
        if p not in metas:
            main_usage.merge(s["usage"])
            main_calls += s["turns"]
            continue
        meta = metas[p]
        s.update(file=os.path.relpath(p, tdir), description=meta.get("description") or "",
                 kind=kind_of(meta, s["prompt"]))
        s["checkpoint"] = CHECKPOINT_RESULT in s["result"]
        s["resumed"] = bool(CHECKPOINT_PROMPT.search(s["prompt"]))
        dispatches.append(s)
    found = sorted({os.path.basename(p)[:-6] for p in mains} |
                   {os.path.basename(os.path.dirname(os.path.dirname(p))) for p in subs})
    return found, main_usage, main_calls, dispatches


# ---- manifests -----------------------------------------------------------------------------------
ID_LINE = re.compile(r"^(\s*)-\s*id:\s*[\"']?([^\"'#\s]+)")
WAVE_LINE = re.compile(r"^\s*wave:\s*[\"']?([^\"'#\s]+)")
FEATURE_LINE = re.compile(r"^feature:\s*[\"']?([^\"'#\s]+)")
TARGET = re.compile(r"\bblock\b\s*(?::\s*`?|`)([\w.-]+)", re.I)
PACK = re.compile(r"packs/([\w.-]+)/([\w.-]+)\.md\b")
HEAD_LINES = 10


def parse_manifest(path):
    """Block ids (and waves) from the top-level `blocks:` list — a minimal line scan, no YAML lib."""
    blocks, feature, inside, indent, cur = [], None, False, None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if re.match(r"^[A-Za-z_][\w-]*:", line):
                fm = FEATURE_LINE.match(line)
                if fm:
                    feature = fm.group(1)
                inside = line.split(":", 1)[0] == "blocks"
                continue
            if not inside:
                continue
            m = ID_LINE.match(line)
            if m and (indent is None or len(m.group(1)) == indent):
                indent = len(m.group(1))
                cur = {"id": m.group(2), "wave": None}
                blocks.append(cur)
                continue
            w = WAVE_LINE.match(line)
            if w and cur is not None and cur["wave"] is None:
                cur["wave"] = w.group(1)
    feature = feature or os.path.basename(os.path.dirname(os.path.abspath(path)))
    for b in blocks:
        b["feature"] = feature
    return blocks


def feature_of_dir(fdir):
    try:
        with open(os.path.join(fdir, "building-blocks.yaml"), encoding="utf-8", errors="replace") as f:
            for line in f:
                m = FEATURE_LINE.match(line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return os.path.basename(os.path.normpath(fdir))


def natural(s):
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"(\d+)", s)]


def mentions(text, ids):
    return [i for i in ids if re.search(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])", text)]


def key_name(key):
    return "%s/%s" % key


class Index:
    """Manifest blocks keyed by (feature, id); an id may exist in several features."""

    def __init__(self, blocks):
        self.blocks = {(b["feature"], b["id"]): b for b in blocks}
        self.by_id = {}
        for f, i in self.blocks:
            self.by_id.setdefault(i, []).append((f, i))
        self.ids = sorted(self.by_id)
        self.features = sorted({f for f, _ in self.blocks})

    def resolve(self, bid, text):
        """The single (feature, id) for an id, using the features the text names; None if ambiguous."""
        keys = self.by_id.get(bid, [])
        if len(keys) > 1:
            named = set(mentions(text, self.features))
            keys = [k for k in keys if k[0] in named]
        return keys[0] if len(keys) == 1 else None

    def attribute(self, dispatch):
        """Explicit target first: the id in the description, a `block <id>` target in the prompt's first
        lines, the pack path; else the only id the prompt mentions. Ambiguous → unattributed."""
        desc, prompt = dispatch["description"], dispatch["prompt"]
        text = desc + "\n" + prompt
        head = "\n".join(prompt.splitlines()[:HEAD_LINES])
        for found in (set(mentions(desc, self.ids)),
                      {m for m in TARGET.findall(head) if m in self.by_id}):
            if len(found) == 1:
                key = self.resolve(found.pop(), text)
                if key:
                    return key
        packs = {k for k in PACK.findall(prompt) if k in self.blocks}
        if len(packs) == 1:
            return packs.pop()
        found = set(mentions(prompt, self.ids))
        if len(found) == 1:
            return self.resolve(found.pop(), text)
        return None


# ---- report --------------------------------------------------------------------------------------
def share(part, whole):
    return round(part / whole, 4) if whole else None


def worker_distribution(workers, prices):
    if not workers:
        return na("no worker dispatches")
    ordered = sorted(workers, key=lambda d: (d["turns"], d["file"]))
    n = len(ordered)
    all_usage = Usage()
    for d in ordered:
        all_usage.merge(d["usage"])
    total_calls = sum(d["turns"] for d in ordered)

    def per_call(group_usage, calls):
        out = {"tokens_per_call": round(group_usage.tokens()["total"] / calls) if calls else None}
        if prices is not None:
            c = group_usage.cost(prices)
            out["cost_per_call_usd"] = round(c / calls, 4) if calls and not isinstance(c, dict) else c
        return out

    quartiles = []
    for q in range(4):
        group = ordered[q * n // 4:(q + 1) * n // 4]
        if not group:
            continue
        u = Usage()
        for d in group:
            u.merge(d["usage"])
        calls = sum(d["turns"] for d in group)
        row = {"quartile": "Q%d" % (q + 1), "sessions": len(group),
               "turns": [group[0]["turns"], group[-1]["turns"]],
               "median_turns": median(d["turns"] for d in group),
               "median_final_context": median(d["final_context"] for d in group)}
        row.update(summarize(u, prices, calls))
        row.update(per_call(u, calls))
        quartiles.append(row)
    top = quartiles[-1]
    out = {"sessions": n, "median_turns": median(d["turns"] for d in ordered),
           "median_final_context": median(d["final_context"] for d in ordered)}
    out.update(summarize(all_usage, prices, total_calls))
    out.update(per_call(all_usage, total_calls))
    out["quartiles"] = quartiles
    out["longest_quartile_share"] = {"tokens": share(top["tokens"]["total"], out["tokens"]["total"])}
    if prices is not None:
        a, b = top["cost_usd"], out["cost_usd"]
        out["longest_quartile_share"]["cost"] = (share(a, b) if not isinstance(a, dict)
                                                 and not isinstance(b, dict) else na("unpriced model"))
    return out


def report(tdir, sessions=None, manifests=(), prices=None, feature_dirs=()):
    found, main_usage, main_calls, dispatches = collect(tdir, sessions)
    total = Usage().merge(main_usage)
    kinds = {}
    for d in dispatches:
        total.merge(d["usage"])
        k = kinds.setdefault(d["kind"], {"dispatches": 0, "calls": 0, "usage": Usage()})
        k["dispatches"] += 1
        k["calls"] += d["turns"]
        k["usage"].merge(d["usage"])
    out = {"source": os.path.abspath(tdir), "sessions": found, "priced": prices is not None,
           "totals": summarize(total, prices, main_calls + sum(d["turns"] for d in dispatches)),
           "main": summarize(main_usage, prices, main_calls), "kinds": {},
           "checkpoints": sum(d["checkpoint"] for d in dispatches),
           "resumed_from_checkpoint": sum(d["resumed"] for d in dispatches)}
    for name in sorted(kinds, key=lambda k: -kinds[k]["usage"].tokens()["total"]):
        k = kinds[name]
        out["kinds"][name] = dict(dispatches=k["dispatches"], **summarize(k["usage"], prices, k["calls"]))
    out["workers"] = worker_distribution([d for d in dispatches if is_worker(d["kind"])], prices)
    if manifests:
        out.update(block_report(dispatches, manifests, prices, feature_dirs))
    elif feature_dirs:
        raise ValueError("--feature-dir needs --manifest")
    return out


def completion(index, feature_dirs):
    """Blocks with completion evidence (`F/integrated/<id>.json`); None without feature dirs."""
    if not feature_dirs:
        return None
    dirs = {}
    for fdir in feature_dirs:
        dirs.setdefault(feature_of_dir(fdir), fdir)
    missing = [f for f in index.features if f not in dirs]
    if missing:
        raise ValueError("--feature-dir: none given for manifest feature(s) %s" % ", ".join(missing))
    return {k for k in index.blocks if os.path.isfile(os.path.join(dirs[k[0]], "integrated", k[1] + ".json"))}


def per_block(usage, prices, n, name):
    out = {"tokens_per_" + name: round(usage.tokens()["total"] / n) if n else None}
    if prices is not None:
        c = usage.cost(prices)
        out["cost_per_%s_usd" % name] = c if isinstance(c, dict) else (round(c / n, 4) if n else None)
    return out


def block_report(dispatches, manifests, prices, feature_dirs=()):
    blocks = []
    for path in manifests:
        blocks += parse_manifest(path)
    index = Index(blocks)
    completed = completion(index, feature_dirs)
    rows, waves = {}, {}
    for d in dispatches:
        key = index.attribute(d)
        r = rows.setdefault(key, {"dispatches": {}, "worker_sessions": 0, "checkpoints": 0, "resumed": 0,
                                  "usage": Usage()})
        r["dispatches"][d["kind"]] = r["dispatches"].get(d["kind"], 0) + 1
        r["worker_sessions"] += is_worker(d["kind"])
        r["checkpoints"] += d["checkpoint"]
        r["resumed"] += d["resumed"]
        r["usage"].merge(d["usage"])
    attributed = Usage()
    out_blocks = {}
    for key in sorted(rows, key=lambda k: (k is None, -rows[k]["usage"].tokens()["total"], k or ("", ""))):
        r = rows[key]
        meta = index.blocks.get(key, {})
        row = {"feature": meta.get("feature"), "id": meta.get("id"), "wave": meta.get("wave"),
               "dispatches": dict(sorted(r["dispatches"].items())), "worker_sessions": r["worker_sessions"],
               "checkpoints": r["checkpoints"], "resumed_from_checkpoint": r["resumed"]}
        if completed is not None and key is not None:
            row["completed"] = key in completed
        row.update(summarize(r["usage"], prices))
        out_blocks[key_name(key) if key else UNATTRIBUTED] = row
        if key is not None:
            attributed.merge(r["usage"])
            wkey = "%s/%s" % (meta.get("feature"), meta.get("wave"))
            w = waves.setdefault(wkey, {"blocks": 0, "usage": Usage()})
            w["blocks"] += 1
            w["usage"].merge(r["usage"])
    dispatched = len([k for k in rows if k is not None])
    att = summarize(attributed, prices)
    summary = {"blocks_in_manifests": len(index.blocks),
               "ids_in_several_features": sorted(i for i, ks in index.by_id.items() if len(ks) > 1),
               "blocks_with_dispatch": dispatched, "attributed_tokens": att["tokens"]["total"],
               "unattributed_tokens": out_blocks.get(UNATTRIBUTED, {}).get("tokens", {}).get("total", 0)}
    if prices is not None:
        summary["attributed_cost_usd"] = att["cost_usd"]
    summary.update(per_block(attributed, prices, dispatched, "dispatched_block"))
    if completed is not None:
        summary["blocks_completed"] = len(completed)
        summary.update(per_block(attributed, prices, len(completed), "completed_block"))
    wave_rows = {k: dict(blocks=v["blocks"], **summarize(v["usage"], prices))
                 for k, v in sorted(waves.items(), key=lambda kv: natural(kv[0]))}
    return {"blocks": out_blocks, "waves": wave_rows, "summary": summary}


# ---- markdown ------------------------------------------------------------------------------------
def fmt(v):
    if isinstance(v, dict) and "n/a" in v:
        return "n/a"
    if v is None:
        return "—"
    if isinstance(v, float) and v.is_integer() and abs(v) >= 1:
        v = int(v)
    if isinstance(v, float):
        return "%.4g" % v if abs(v) < 1 else "{:,.2f}".format(v)
    if isinstance(v, int):
        return "{:,}".format(v)
    return str(v)


def md_table(head, rows):
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def tok_cols(r, priced):
    t = r["tokens"]
    cols = [t[c] for c in CLASSES] + [t["total"]]
    return cols + ([r.get("cost_usd")] if priced else [])


def markdown(rep):
    priced = rep["priced"]
    th = list(CLASSES) + ["total"] + (["USD"] if priced else [])
    out = ["# Run cost — %s" % rep["source"], "",
           "Sessions: %s. %s" % (", ".join(rep["sessions"]) or "none",
                                 "" if priced else "Tokens only (no `--prices`)."), "", "## Per agent kind", ""]
    rows = [["(total)", "", rep["totals"]["calls"]] + tok_cols(rep["totals"], priced),
            [MAIN, "", rep["main"]["calls"]] + tok_cols(rep["main"], priced)]
    rows += [[k, v["dispatches"], v["calls"]] + tok_cols(v, priced) for k, v in rep["kinds"].items()]
    out += [md_table(["kind", "dispatches", "calls"] + th, rows), "", "## Worker sessions by turns", ""]
    w = rep["workers"]
    if "n/a" in w:
        out.append("n/a — " + w["n/a"])
    else:
        head = ["quartile", "sessions", "turns", "median turns", "median final ctx", "tokens", "tokens/call"]
        head += ["USD", "USD/call"] if priced else []
        rows = []
        for q in w["quartiles"] + [dict(w, quartile="all", turns=None)]:
            turns = "%d–%d" % tuple(q["turns"]) if q["turns"] else ""
            row = [q["quartile"], q.get("sessions"), turns, q["median_turns"], q["median_final_context"],
                   q["tokens"]["total"], q["tokens_per_call"]]
            rows.append(row + ([q["cost_usd"], q["cost_per_call_usd"]] if priced else []))
        out.append(md_table(head, rows))
        s = w["longest_quartile_share"]
        out += ["", "Longest quartile share: %s of worker tokens%s." % (
            fmt(s["tokens"]), ", %s of worker cost" % fmt(s["cost"]) if priced else "")]
    if "blocks" in rep:
        sm = rep["summary"]
        line = "Blocks with ≥1 dispatch: %d of %d; tokens per dispatched block: %s" % (
            sm["blocks_with_dispatch"], sm["blocks_in_manifests"], fmt(sm["tokens_per_dispatched_block"]))
        if priced:
            line += " (USD %s)" % fmt(sm["cost_per_dispatched_block_usd"])
        if "blocks_completed" in sm:
            line += ". Completed (integrated): %d; tokens per completed block: %s" % (
                sm["blocks_completed"], fmt(sm["tokens_per_completed_block"]))
            if priced:
                line += " (USD %s)" % fmt(sm["cost_per_completed_block_usd"])
        line += ". Unattributed: %s tokens. Checkpoints: %d; resumed sessions: %d." % (
            fmt(sm["unattributed_tokens"]), rep["checkpoints"], rep["resumed_from_checkpoint"])
        out += ["", "## Per block", "", line, ""]
        has_done = "blocks_completed" in sm
        rows = []
        for b, r in rep["blocks"].items():
            kinds = ", ".join("%s %d" % (k.split(":")[-1], n) for k, n in r["dispatches"].items())
            row = [b, r["wave"], kinds, r["worker_sessions"], r["checkpoints"], r["resumed_from_checkpoint"]]
            row += [("yes" if r["completed"] else "no") if "completed" in r else ""] if has_done else []
            rows.append(row + [r["tokens"]["total"]] + ([r["cost_usd"]] if priced else []))
        head = ["block", "wave", "dispatches", "worker sessions", "checkpoints", "resumed"]
        out.append(md_table(head + (["completed"] if has_done else []) + ["tokens"] + (["USD"] if priced else []),
                            rows))
        out += ["", "## Per wave", ""]
        rows = [[k, v["blocks"], v["tokens"]["total"]] + ([v["cost_usd"]] if priced else [])
                for k, v in rep["waves"].items()]
        out.append(md_table(["feature/wave", "blocks", "tokens"] + (["USD"] if priced else []), rows))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("transcripts", help="a Claude Code project transcript directory")
    ap.add_argument("--session", action="append", help="restrict to this session id (repeatable)")
    ap.add_argument("--manifest", action="append", default=[], help="building-blocks.yaml (repeatable)")
    ap.add_argument("--feature-dir", action="append", default=[],
                    help="feature folder of a manifest; `integrated/<id>.json` marks a completed block (repeatable)")
    ap.add_argument("--prices", help="JSON {model-family: {input, cache_write, cache_read, output}} USD per Mtok")
    ap.add_argument("--md", action="store_true", help="Markdown tables instead of JSON")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.transcripts):
        ap.error("not a directory: %s" % a.transcripts)
    try:
        prices = None
        if a.prices:
            with open(a.prices, encoding="utf-8") as f:
                prices = load_prices(json.load(f))
        rep = report(a.transcripts, a.session, a.manifest, prices, a.feature_dir)
    except (OSError, ValueError) as e:
        ap.error(str(e))
    sys.stdout.write(markdown(rep) if a.md else json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
