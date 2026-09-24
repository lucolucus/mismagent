#!/usr/bin/env python3
"""Benchmark scorer: compare runs of the SAME deliverable built with different mismAgent versions.

Zero-cost and deterministic: stdlib only, no LLM, no network, no build tool is run. It only reads
the run folders (git is queried read-only). A metric that cannot be computed prints `n/a`; the JSON
output (`--json`) carries the reason.

    python3 bench/score.py ~/projects/mismagent-test/RegistratoreCassa{2,3,4,5} [--json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

PLUGINS_JSON = os.path.expanduser("~/.claude/plugins/installed_plugins.json")
SKIP_DIRS = {".git", ".worktrees", ".gradle", "build", "node_modules", ".idea", ".kotlin", ".serena", ".claude",
             ".mismagent", "bin", "obj", "dist", "out", "target", "generated", "__pycache__",
             ".venv", "venv", "gradle", ".vscode"}
LANG = {".kt": "Kotlin", ".java": "Java", ".scala": "Scala", ".py": "Python", ".cs": "C#",
        ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
        ".swift": "Swift", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".sq": "SQL"}
MODEL_EXT = {".md", ".yaml", ".yml", ".json", ".txt"}
CASE_MARKERS = {  # per extension: regexes whose matches are test cases
    ".kt": [r"@(?:Test|ParameterizedTest)\b"], ".java": [r"@(?:Test|ParameterizedTest)\b"],
    ".scala": [r"@Test\b"], ".py": [r"^\s*(?:async\s+)?def test_\w*"],
    ".ts": [r"^\s*(?:it|test)(?:\.\w+)?\s*\("], ".tsx": [r"^\s*(?:it|test)(?:\.\w+)?\s*\("],
    ".js": [r"^\s*(?:it|test)(?:\.\w+)?\s*\("], ".jsx": [r"^\s*(?:it|test)(?:\.\w+)?\s*\("],
    ".cs": [r"\[(?:Fact|Theory|Test|TestMethod|TestCase)\b"], ".swift": [r"^\s*func test\w*"],
    ".go": [r"^func Test\w*"], ".rs": [r"#\[test\]"], ".rb": [r"^\s*it\s+['\"]"]}
KT_BACKTICK_FUN = re.compile(r"^\s*fun\s+`", re.M)
MOVEMENTS = ("explore", "model", "build")


def na(reason):
    return {"n/a": reason}


def is_na(v):
    return isinstance(v, dict) and "n/a" in v


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# ---- files -------------------------------------------------------------------------------------
def walk(root, skip=SKIP_DIRS):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in skip)
        for f in sorted(files):
            yield os.path.join(d, f)


def is_test_path(rel):
    parts = rel.split(os.sep)
    for p in parts[:-1]:
        if p in ("test", "tests", "__tests__", "spec") or re.fullmatch(r"[a-z]\w*Test|.+\.Tests?", p):
            return True
    name = parts[-1]
    return bool(re.match(r"test_.*\.py$|.*_test\.(py|go)$|.*Tests?\.(kt|java|cs|swift|scala)$"
                         r"|.*\.(test|spec)\.[jt]sx?$", name))


def source_files(root):
    """[(rel, ext, is_test)] for every source file outside build/tool dirs."""
    out = []
    for p in walk(root):
        ext = os.path.splitext(p)[1]
        if ext in LANG:
            rel = os.path.relpath(p, root)
            out.append((rel, ext, is_test_path(rel)))
    return out


def count_cases(ext, text):
    n = sum(len(re.findall(rx, text, re.M)) for rx in CASE_MARKERS.get(ext, []))
    if n == 0 and ext == ".kt":  # kotlin.test without @Test annotations is rare; backtick funs
        n = len(KT_BACKTICK_FUN.findall(text))
    return n


def nonblank(text):
    return sum(1 for line in text.splitlines() if line.strip())


# ---- 1. version --------------------------------------------------------------------------------
def version(root, plugins_json):
    found, where = [], []
    try:
        data = json.loads(read(plugins_json) or "{}")
    except ValueError:
        data = {}
    real = os.path.realpath(root)
    for key, entries in (data.get("plugins") or {}).items():
        if not key.split("@")[0].startswith("mismagent"):
            continue
        for e in entries:
            if e.get("projectPath") and os.path.realpath(e["projectPath"]) == real:
                v = os.path.basename(os.path.normpath(e.get("installPath", ""))) or e.get("version")
                if v and v not in found:
                    found.append(v)
    if found:
        where.append("plugin " + ", ".join(found))
    head = "\n".join(read(os.path.join(root, "MISMAGENT-LOG.md")).splitlines()[:15])
    m = re.search(r"mismAgent\s*v?(\d+\.\d+(?:\.\d+)?)", head, re.I) or \
        re.search(r"\bv(\d+\.\d+(?:\.\d+)?)\b", head)
    if m:
        where.append("log " + m.group(1))
    return " · ".join(where) if where else na("no installed_plugins entry for this path, "
                                              "no version in the log header")


# ---- 2. requirements coverage ------------------------------------------------------------------
REQ_ROW = re.compile(r"^\|\s*([A-Z]{1,6}\d+(?:\.\d+)*)\s*\|(.*)$", re.M)
TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,6}\d+(?:\.\d+)*)(\.\*)?(?!\w)")
RANGE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,6})(\d+(?:\.\d+)*)\s*(?:–|—|-|\.\.)\s*(?:\1)?(\d+(?:\.\d+)*)")


def requirements(root):
    """{id: is_high} in document order, from the ID column of REQUISITI.md's tables."""
    text = read(os.path.join(root, "REQUISITI.md"))
    reqs = {}
    for m in REQ_ROW.finditer(text):
        reqs.setdefault(m.group(1), "🔴" in m.group(2))
    return reqs


def cited(text, reqs):
    ids, order, out = set(reqs), list(reqs), set()
    for m in TOKEN.finditer(text):
        tok, wild = m.group(1), m.group(2)
        if wild:  # RF6.* → every RF6.x
            out.update(i for i in ids if i.startswith(tok + "."))
        elif tok in ids:
            out.add(tok)
    for m in RANGE.finditer(text):  # RF2.1–RF2.5 / RF2.1-2.5
        a, b = m.group(1) + m.group(2), m.group(1) + m.group(3)
        if a in ids and b in ids and order.index(a) < order.index(b):
            out.update(order[order.index(a):order.index(b) + 1])
    return out


def model_text(root):
    md = os.path.join(root, ".mismagent")
    if not os.path.isdir(md):
        return None
    return "\n".join(read(p) for p in walk(md, skip={".git"}) if os.path.splitext(p)[1] in MODEL_EXT)


# ---- 5. friction -------------------------------------------------------------------------------
ENTRY_HEAD = re.compile(r"^#{2,4}\s.*?#(\d+)\b")
CLASS_LINE = re.compile(r"^\s*[-*]?\s*\**\s*(?:classification|class|tipo|type)\s*\**\s*:\s*\**(.*)", re.I)
WHEN_LINE = re.compile(r"^\s*[-*]?\s*\**\s*(?:when|quando|dove|where)\b[^:]*:\s*\**(.*)", re.I)
MOVEMENT_HEAD = re.compile(r"^(#{1,3})\s*(?:movimento|movement)\s*:\s*(\w+)", re.I)


def classify(text):
    t = re.split(r"\s[—–]\s|\s-\s", text.lower())[0]  # the verdict, not the commentary after a dash
    core = bool(re.search(r"\bcore\b", t))
    prof = bool(re.search(r"\bprofil[eo]\b|project binding", t))
    return "both" if core and prof else "core" if core else "profile" if prof else "unclassified"


def movement(text):
    t = (text or "").lower().replace("build-manifest", "model")  # a model step despite its name
    hits = [(m.start(), m.group(0)) for m in re.finditer("|".join(MOVEMENTS), t)]
    return min(hits)[1] if hits else None


def parse_friction(text):
    """[{id, class, movement}] from heading entries (## #N — …) or a table with a CORE/PROFILO column."""
    entries, cur, section = [], None, (0, None)  # section = (heading level, movement)
    table_cols = None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            low = [c.lower() for c in cells]
            if any("core/profil" in c or c in ("class", "classe", "tipo") for c in low):
                table_cols = low
                continue
            if table_cols and cells and re.fullmatch(r"\d+", cells[0]):
                row = dict(zip(table_cols, cells))
                cls = next((v for k, v in row.items() if "core/profil" in k or k in ("class", "classe", "tipo")), "")
                when = next((v for k, v in row.items() if k in ("quando", "when")), "")
                entries.append({"id": int(cells[0]), "class": classify(cls), "movement": movement(when)})
            continue
        m = MOVEMENT_HEAD.match(line)
        if m:
            section = (len(m.group(1)), movement(m.group(2)))
            continue
        m = ENTRY_HEAD.match(line)
        if m:
            level = len(line) - len(line.lstrip("#"))
            if level <= section[0]:
                section = (0, None)  # an entry at the section's level closes the section
            paren = " ".join(re.findall(r"\(([^)]*)\)", line.split("—", 2)[1] if "—" in line else ""))
            cur = {"id": int(m.group(1)), "class": None, "movement": None, "_head": paren,
                   "_section": section[1]}
            entries.append(cur)
            continue
        if line.startswith("## ") or line.startswith("# "):
            cur = None  # a non-entry section (ideas, change notes) ends the current entry
            continue
        if cur is None:
            continue
        m = CLASS_LINE.match(line)
        if m and cur["class"] is None:
            cur["class"] = classify(m.group(1))
        m = WHEN_LINE.match(line)
        if m and cur["movement"] is None:
            cur["movement"] = movement(m.group(1))
    for e in entries:
        if e.get("class") is None:
            e["class"] = classify(e.get("_head", ""))
        if e.get("movement") is None:  # the When field wins over the enclosing section
            e["movement"] = e.get("_section")
        e.pop("_head", None)
        e.pop("_section", None)
    return entries


def friction(root):
    path = os.path.join(root, "MISMAGENT-LOG.md")
    if not os.path.isfile(path):
        return na("no MISMAGENT-LOG.md")
    es = parse_friction(read(path))
    out = {"entries": len(es)}
    for k in ("core", "profile", "both", "unclassified"):
        out[k] = sum(e["class"] == k for e in es)
    for k in MOVEMENTS + (None,):
        out["mv_" + (k or "unknown")] = sum(e["movement"] == k for e in es)
    return out


# ---- 6. process --------------------------------------------------------------------------------
def process(root):
    md = os.path.join(root, ".mismagent")
    if not os.path.isdir(md):
        return na("no .mismagent/")
    states = {s: 0 for s in ("backlog", "todo", "doing", "done")}
    seen_states, oq, rework, integrated, dnotes, adrs = False, 0, 0, 0, 0, 0
    notes_files = 0
    for d, dirs, files in os.walk(md):
        base, parent2 = os.path.basename(d), os.path.basename(os.path.dirname(os.path.dirname(d)))
        mds = [f for f in files if f.endswith(".md")]
        if base in states and parent2 in ("blocks", "tasks"):
            seen_states = True
            states[base] += len(mds)
        elif base == "open-questions":
            oq += len(mds)
        elif base == "rework":
            rework += len(mds)
        elif base == "integrated":
            integrated += len([f for f in files if f.endswith(".json")])
        elif base == "decisions":
            adrs += len([f for f in mds if re.match(r"\d{3,4}-", f)])
        if "decisions.md" in files:
            notes_files += 1
            dnotes += len(re.findall(r"^#{2,4}\s*D-\d+", read(os.path.join(d, "decisions.md")), re.M))
    return {"blocks": states if seen_states else na("no blocks/<ctx>/<state>/ or tasks/<side>/<state>/ dirs"),
            "open_questions": oq, "rework": rework, "integrated": integrated,
            "decision_notes": dnotes if notes_files else na("no decisions.md"), "adrs": adrs}


# ---- 7. git ------------------------------------------------------------------------------------
def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def git_stats(root):
    if not os.path.exists(os.path.join(root, ".git")):
        return na("not a git repository")
    branches = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    dates = git(root, "log", "--all", "--format=%cI")
    if dates is None or not dates:
        return {"commits": 0, "branches": len((branches or "").split()),
                "first": na("no commits"), "last": na("no commits"), "span_days": na("no commits")}
    ds = sorted(datetime.fromisoformat(x) for x in dates.split())
    return {"commits": len(ds), "branches": len(branches.split()) if branches else 0,
            "first": ds[0].date().isoformat(), "last": ds[-1].date().isoformat(),
            "span_days": (ds[-1] - ds[0]).days}


# ---- per run -----------------------------------------------------------------------------------
def score(root, plugins_json=PLUGINS_JSON):
    r = {"run": os.path.basename(os.path.normpath(root)), "path": os.path.abspath(root)}
    r["version"] = version(root, plugins_json)
    files = source_files(root)
    main = [(f, e) for f, e, t in files if not t]
    test = [(f, e) for f, e, t in files if t]
    main_txt = {f: read(os.path.join(root, f)) for f, _ in main}
    test_txt = {f: read(os.path.join(root, f)) for f, _ in test}
    # tests
    per_lang, n_files, n_cases = {}, 0, 0
    for f, e in test:
        c = count_cases(e, test_txt[f])
        if c:
            n_files += 1
            n_cases += c
            per_lang[LANG[e]] = per_lang.get(LANG[e], 0) + c
    none = na("no test sources found")
    r["test_files"] = n_files if test else none
    r["test_cases"] = n_cases if test else none
    r["test_cases_by_lang"] = per_lang if test else none
    r["main_loc"] = sum(map(nonblank, main_txt.values())) if main else na("no main sources found")
    r["test_loc"] = sum(map(nonblank, test_txt.values())) if test else none
    langs = sorted({LANG[e] for _, e in main + test} - {"SQL"})
    r["languages"] = ", ".join(langs) if langs else na("no sources found")
    # requirements
    reqs = requirements(root)
    if not reqs:
        for k in ("req_ids", "req_model", "req_tests", "req_main", "req_high_tests"):
            r[k] = na("no requirement IDs in REQUISITI.md")
    else:
        high = {i for i, h in reqs.items() if h}
        r["req_ids"] = len(reqs)
        mt = model_text(root)
        r["req_model"] = sorted(cited(mt, reqs)) if mt is not None else na("no .mismagent/")
        r["req_tests"] = sorted(cited("\n".join(test_txt.values()), reqs)) if test else none
        r["req_main"] = sorted(cited("\n".join(main_txt.values()), reqs)) if main else na("no main sources")
        if not high:
            r["req_high_tests"] = na("no 🔴 requirements")
        elif is_na(r["req_tests"]):
            r["req_high_tests"] = r["req_tests"]
        else:
            r["req_high_tests"] = {"covered": len(high & set(r["req_tests"])), "of": len(high)}
    r["friction"] = friction(root)
    r["process"] = process(root)
    r["git"] = git_stats(root)
    r["gate"] = na("not executed: builds would write into the run (future work)")
    return r


# ---- output ------------------------------------------------------------------------------------
def pick(r, path):
    v = r
    for k in path.split("."):
        if is_na(v):
            return v
        v = v.get(k) if isinstance(v, dict) else None
        if v is None:
            return na("missing")
    return v


def cell(v, total=None):
    if is_na(v):
        return "n/a"
    if isinstance(v, list):
        return "%d/%d" % (len(v), total) if total else str(len(v))
    if isinstance(v, dict) and "covered" in v:
        return "%d%% (%d/%d)" % (round(100 * v["covered"] / v["of"]), v["covered"], v["of"])
    if isinstance(v, dict):
        return ", ".join("%s %s" % (k, x) for k, x in v.items()) or "-"
    return str(v)


ROWS = [("mismAgent version", "version"), ("languages", "languages"),
        ("requirement IDs", "req_ids"), ("req cited in model", "req_model"),
        ("req cited in tests", "req_tests"), ("req cited in main", "req_main"),
        ("🔴 req covered by tests", "req_high_tests"),
        ("test files", "test_files"), ("test cases", "test_cases"),
        ("main LOC (non-blank)", "main_loc"), ("test LOC (non-blank)", "test_loc"),
        ("friction entries", "friction.entries"), ("friction core", "friction.core"),
        ("friction profile", "friction.profile"), ("friction both", "friction.both"),
        ("friction unclassified", "friction.unclassified"),
        ("friction explore/model/build/?", "friction"),
        ("blocks todo/doing/done", "process.blocks"), ("blocks backlog", "process.blocks.backlog"),
        ("open questions", "process.open_questions"), ("rework files", "process.rework"),
        ("integrated", "process.integrated"), ("decision notes (D-)", "process.decision_notes"),
        ("ADRs", "process.adrs"), ("git commits", "git.commits"), ("git first commit", "git.first"),
        ("git last commit", "git.last"), ("git span (days)", "git.span_days"),
        ("git branches", "git.branches"), ("gate", "gate")]


def table(results):
    out = ["| metric | " + " | ".join(r["run"] for r in results) + " |",
           "|---|" + "---|" * len(results)]
    for label, key in ROWS:
        cells = []
        for r in results:
            v = pick(r, key)
            if key == "friction" and not is_na(v):
                v = "/".join(str(v["mv_" + k]) for k in MOVEMENTS + ("unknown",))
            elif key == "process.blocks" and not is_na(v):
                v = "%d/%d/%d" % (v["todo"], v["doing"], v["done"])
            total = r["req_ids"] if key.startswith("req_") and not is_na(r.get("req_ids")) else None
            cells.append(cell(v, total))
        out.append("| %s | %s |" % (label, " | ".join(cells)))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="+", help="run folders (each with REQUISITI.md)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--plugins-json", default=PLUGINS_JSON, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    missing = [p for p in a.runs if not os.path.isdir(p)]
    if missing:
        ap.error("not a directory: " + ", ".join(missing))
    results = [score(p, a.plugins_json) for p in a.runs]
    print(json.dumps(results, indent=2, ensure_ascii=False) if a.json else table(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
