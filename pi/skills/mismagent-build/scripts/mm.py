#!/usr/bin/env python3
"""mm — the deterministic tool of mismAgent 0.7 (Python 3 stdlib only).

Owns ALL the git and all the counting of the slice lifecycle; no prompt carries it. Works on the
git repository containing the cwd. No branches: one slice at a time on the current branch; `start`
records Base, the reviewer reviews Base..HEAD, a REWORK adds commits, nothing reaches done/ without
a PASS at HEAD and a green gate. Exit: 0 ok · 1 check/gate failure or refused precondition (one
line on stderr) · 2 usage. Files, parsed line by line (forgiving about whitespace and **bold**):
  AGENTS.md `## mismagent`: `- key: value` — test, lint, smoke, max_file_lines (400), suppressions (0),
    acceptance (tests/acceptance; comma-separated folders, for a build that wants tests elsewhere)
  .mismagent/examples/<capability>.md: | id | given | when | then | rule | req | release |, ids EX-<n>
    unique across the files; a `then` containing `(superseded by EX-<n>)` retires the row (no
    acceptance marker required). The old single .mismagent/examples.md is still read, with a warning
  .mismagent/brief.md: one page (a warning above BRIEF_WORDS): decisions go to decisions/, a
    release's scope and open questions to releases/<release>.md
  .mismagent/slices/{todo,doing,done}/NN-name.md: Kind: Release: Examples: Base: After:,
    ## Question/Answer, ## Progress (the builder's, when it returns) — After: lists slices (NN or
    stem) that must be done before it starts
  .mismagent/reviews/{<slice-stem>,<release>}-<k>.md: VERDICT:, SHA: — "at HEAD" = SHA (>= 7 hex)
    is a prefix of HEAD
  .mismagent/design-notes.md: one note per `- ` line · <acceptance>/**: markers EX-<n> (not E501)
  .mismagent/conventions-proposals.md: one proposal per `- ` line (create or update a topic)
  .mismagent/stack-reviews/N-status.md: `state:` open|decided|done — any not done holds `next`
    (`idle`): the stack is in question until specify's review and its handoff are finished
  .agents/skills/conventions/**.md: the project's conventions skill, written with the human in
    /skill:mismagent-conventions; every `path` it cites must exist
Design choices:
- Dirty tree = `git status` (which honours .gitignore) minus .mismagent/reviews/ and
  .mismagent/design-notes.md (the reviewer writes them after the HEAD it reviewed; `mm land` commits
  them) and minus untracked run debris (__pycache__/, *.pyc, .pytest_cache/, *.db, *.sqlite*, *.log).
- Base = the HEAD `start` began from (a commit cannot carry its own SHA). A doing slice has work when
  Base..HEAD changes something outside .mismagent/; no work -> `build`. With work, a clean tree and
  no review at HEAD: `review` only if the slice file has a `## Progress` section (or, from before
  0.7.2, progress.md a `## <slice stem>` heading), else `resume`.
- Verdicts are checked against SCORES (`name=<n>`, `-` = not assessed): PASS with a score < 4 counts
  as REWORK, HEALTHY with a score < 4 as DESIGN-PASS. The architect answers an escalation with
  VERDICT: DIRECT (-> `rework` following it) or PASS; a REWORK after a DIRECT -> `stuck` (human).
- A DESIGN-PASS release review at HEAD asks for a pass unless two DESIGN-PASS reviews of that
  release came before it (two passes ran): then `confirm`.
- check --base guards REQUISITI*, requirements*.md (not requirements.txt, a dependency list),
  the examples and the conventions skill; a modified (or renamed and edited) acceptance test is an error only while
  the doing slice is a feature and the file names none of its examples nor a superseded one.
- Sensors: suppressions over tracked code files outside .mismagent/; size also skips tests/.
- No word cap on .mismagent/ as a whole: each thing has its file (a capability's examples, a
  decision, a release, a slice and its progress), so agents read the files they need, never the
  history whole; what lasts is kept current in the skill and ARCHITECTURE.md, not compacted.
- `park` puts a doing slice back in todo only while it has no work since Base (a stack change
  that must come first): half-done work never leaves doing unreviewed. A todo slice whose After:
  slices are not all done is skipped by `next`; when every todo slice waits -> `idle`.
- Agents only propose conventions; with no slice doing, a pending proposal (or a done model slice
  and no skill yet) -> `conventions`: the human decides before the next slice starts.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

KINDS = ("model", "feature", "refactor")
STATES = ("todo", "doing", "done")
M = ".mismagent"
EXAMPLES, OLD_EXAMPLES, BRIEF = M + "/examples", M + "/examples.md", M + "/brief.md"
NOTES, REVIEWS, OLD_PROGRESS = M + "/design-notes.md", M + "/reviews", M + "/progress.md"
BRIEF_WORDS = 600
TOPIC_WORDS = 300
SKILL, PROPOSALS = ".agents/skills/conventions", M + "/conventions-proposals.md"
STACK_REVIEWS = M + "/stack-reviews"
CITED = re.compile(r"`([\w.\-/]+)`")
IGNORED_DIRTY = (REVIEWS + "/", NOTES)
DEBRIS = re.compile(r"(^|/)(__pycache__|\.pytest_cache)/|\.pyc$|\.db$|\.sqlite[^/]*$|\.log$")
EX_ID = re.compile(r"^EX-\d+$")
EX_MARK = re.compile(r"(?<![\w-])EX-\d+(?!\d)")
SUPERSEDED = re.compile(r"\(\s*superseded\s+by\s+EX-\d+\s*\)", re.I)
SUPPRESS = re.compile(r"noqa|pylint:\s*disable|eslint-disable|@SuppressWarnings|type:\s*ignore|nolint")
SOURCE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
              ".kts", ".rb", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".swift", ".php", ".scala",
              ".vue", ".svelte", ".dart", ".ex", ".exs", ".lua", ".sh", ".m", ".fs", ".clj"}
MAX_REWORK, MAX_DESIGN_PASSES, NOTES_LIMIT = 2, 2, 5
ROOT = "."

class Refused(Exception):
    """A refused precondition or a failure: one line on stderr, exit 1."""

def need(ok, msg):
    if not ok:
        raise Refused(msg)

def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and p.returncode:
        msg = (p.stderr or p.stdout).strip().splitlines()
        raise Refused("git %s: %s" % (args[0], msg[-1] if msg else "failed"))
    return p.stdout

def head():
    return git("rev-parse", "HEAD").strip()

def read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""

def config():
    cfg, inside = {}, False
    for line in read("AGENTS.md").splitlines():
        s = line.strip()
        if s.startswith("#"):
            inside = re.fullmatch(r"##\s+mismagent\s*", s, re.I) is not None
            continue
        m = re.match(r"^[-*]\s*([\w-]+)\s*:\s*(.*)$", s)
        if inside and m:
            v = m.group(2).strip()
            cfg[m.group(1).lower()] = v[1:-1] if len(v) > 1 and v[0] == v[-1] == "`" else v
    return cfg

def cfg_int(cfg, key, default):
    return int(cfg[key]) if cfg.get(key, "").isdigit() else default

def example_files():
    old = [OLD_EXAMPLES] if os.path.isfile(os.path.join(ROOT, OLD_EXAMPLES)) else []
    return old + sorted(r for r in walk(EXAMPLES) if r.endswith(".md"))

def examples():
    """-> (rows [{id, release, superseded, file}], errors)."""
    rows, errors = [], []
    for rel, n, line in ((rel, n, line) for rel in example_files()
                         for n, line in enumerate(read(rel).splitlines(), 1)):
        s = line.strip()
        if not s.startswith("|") or ("-" in s and re.fullmatch(r"[|:\-\s]+", s)):
            continue
        cells = [c.strip() for c in (s[1:-1] if s.endswith("|") and len(s) > 1 else s[1:]).split("|")]
        if cells[0].lower() == "id":
            continue
        where = "%s:%d" % (rel, n)
        if len(cells) != 7:
            errors.append("%s: %d columns, expected 7 (id given when then rule req release)"
                          % (where, len(cells)))
        elif not EX_ID.match(cells[0]):
            errors.append("%s: id %r is not EX-<n>" % (where, cells[0]))
        elif not cells[6]:
            errors.append("%s: %s has no release" % (where, cells[0]))
        else:
            rows.append({"id": cells[0], "release": cells[6], "file": rel,
                         "superseded": bool(SUPERSEDED.search(cells[3]))})
    ids = [r["id"] for r in rows]
    errors += ["duplicate example id %s (%s)" % (i, ", ".join(r["file"] for r in rows if r["id"] == i))
               for i in sorted(set(ids)) if ids.count(i) > 1]
    return rows, errors

def parse_slice(state, name):
    rel = "%s/slices/%s/%s" % (M, state, name)
    s = {"state": state, "stem": name[:-3], "path": rel, "kind": "", "release": "",
         "examples": [], "bad_examples": [], "base": "", "after": []}
    num = re.match(r"(\d+)", name)
    s["num"] = int(num.group(1)) if num else 10 ** 9
    sections = []  # [heading, non-empty lines], in order
    for line in read(rel).splitlines():
        st = line.strip()
        h = re.match(r"^##\s+(.*)$", st)
        if h:
            sections.append([h.group(1).strip().lower(), []])
            continue
        if sections:
            if st:
                sections[-1][1].append(st)
            continue
        hm = re.match(r"^(kind|release|examples|base|after)\s*:\s*(.*)$", st.lstrip("-* ").replace("**", ""), re.I)
        if hm:
            key, val = hm.group(1).lower(), hm.group(2).strip()
            if key == "examples":
                toks = [t for t in re.split(r"[,\s]+", val) if t and t not in ("-", "—", "none")]
                s["examples"] = [t for t in toks if EX_ID.match(t)]
                s["bad_examples"] = [t for t in toks if not EX_ID.match(t)]
            elif key == "after":
                s["after"] = [t for t in re.split(r"[,\s]+", val) if t and t not in ("-", "—", "none")]
            else:
                s[key] = val.split()[0] if val else ""
    s["kind"] = s["kind"].lower()
    q = max((i for i, (name, _) in enumerate(sections) if name == "question"), default=-1)
    answered = max((i for i, (name, body) in enumerate(sections) if name == "answer" and body), default=-1)
    s["blocked"] = q > answered and bool(sections[q][1])  # an empty ## Answer answers nothing
    return s

def ls(rel):
    d = os.path.join(ROOT, rel)
    return sorted(os.listdir(d)) if os.path.isdir(d) else []

def slices():
    return [parse_slice(st, n) for st in STATES for n in ls("%s/slices/%s" % (M, st)) if n.endswith(".md")]

def find_slice(arg, sls):
    stem = os.path.basename(arg)
    stem = stem[:-3] if stem.endswith(".md") else stem
    hits = [s for s in sls if s["stem"] == stem] or [s for s in sls if s["stem"].startswith(stem + "-")]
    need(len(hits) == 1, "slice %r: %s" % (arg, "not found" if not hits else "ambiguous"))
    return hits[0]

DEMOTE = {"PASS": "REWORK", "HEALTHY": "DESIGN-PASS"}

def dep(ref, sls):
    """The slice an After: reference names (its number or its stem), or None."""
    hits = [s for s in sls if s["stem"] == ref or (ref.isdigit() and s["num"] == int(ref))]
    return hits[0] if len(hits) == 1 else None

def waits_for(s, sls):
    """The After: references of s not yet done."""
    return [r for r in s["after"] if not (dep(r, sls) and dep(r, sls)["state"] == "done")]

def open_stack_reviews():
    """Stack reviews whose N-status.md does not say `state: done` (specify's review, then handoff)."""
    rels = [r for r in ls(STACK_REVIEWS) if r.endswith("-status.md")]
    return [r[:-len("-status.md")] for r in rels if not re.search(
        r"^[-*\s]*state\s*:\s*(?:\*\*\s*)?done\b", read("%s/%s" % (STACK_REVIEWS, r)).replace("**", ""),
        re.M | re.I)]

def reviews(prefix):
    """-> [{k, verdict, sha, path, why}] of <prefix>-<k>.md sorted by k; `verdict` is the one that
    counts: a PASS/HEALTHY with an assessed score < 4 is demoted (REWORK/DESIGN-PASS), `why` says so."""
    out = []
    for name in ls(REVIEWS):
        m = re.fullmatch(re.escape(prefix) + r"-(\d+)\.md", name)
        if not m:
            continue
        path = "%s/%s" % (REVIEWS, name)
        text = read(path)
        v = re.search(r"^[\s*_>-]*VERDICT[\s*_]*:[\s*_]*([A-Za-z-]+)", text, re.M | re.I)
        sha = re.search(r"^[\s*_>-]*SHA[\s*_]*:[\s*_`]*([0-9a-fA-F]+)", text, re.M | re.I)
        scores = re.search(r"^[\s*_>-]*SCORES[\s*_]*:(.*)$", text, re.M | re.I)
        low = re.findall(r"([\w-]+)\s*=\s*([0-3])(?!\d)", scores.group(1)) if scores else []
        r = {"k": int(m.group(1)), "verdict": v.group(1).upper() if v else "", "path": path,
             "sha": sha.group(1).lower() if sha else "", "why": ""}
        if low and r["verdict"] in DEMOTE:
            r["why"] = "%s with %s < 4 counts as %s" % (r["verdict"], " ".join("=".join(x) for x in low),
                                                       DEMOTE[r["verdict"]])
            r["verdict"] = DEMOTE[r["verdict"]]
        out.append(r)
    return sorted(out, key=lambda r: r["k"])

def at_head(revs, sha):
    hits = [r for r in revs if len(r["sha"]) >= 7 and sha.startswith(r["sha"])]
    return hits[-1] if hits else None

def said(r, text):
    return "review %d %s" % (r["k"], r["why"] or text)

def dirty():
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        p = line[3:].split(" -> ")[-1].strip('"')
        if not (any(p == i or p.startswith(i) for i in IGNORED_DIRTY)
                or (line.startswith("??") and DEBRIS.search(p))):
            return True
    return False

def walk(top):
    for dirpath, _, names in os.walk(os.path.join(ROOT, top)):
        for name in names:
            yield os.path.relpath(os.path.join(dirpath, name), ROOT)

def acceptance():
    """The acceptance folders: AGENTS.md `acceptance:` (comma-separated), else tests/acceptance."""
    return [d.strip().strip("/") for d in config().get("acceptance", "").split(",") if d.strip()] \
        or ["tests/acceptance"]

def markers():
    """-> {EX-id: [files]} from the acceptance folders."""
    found = {}
    for rel in (r for d in acceptance() for r in walk(d)):
        for ex in set(EX_MARK.findall(read(rel))):
            found.setdefault(ex, []).append(rel)
    return found

def unmarked(s, marks, retired):
    """The slice's examples with no acceptance marker (a superseded one needs none)."""
    return [ex for ex in s["examples"] if ex not in marks and ex not in retired]

def count_items(rel):
    return sum(1 for line in read(rel).splitlines() if line.lstrip().startswith("- "))

def release_order(exs, sls):
    tokens = [e["release"] for e in exs] + [s["release"] for s in sorted(sls, key=lambda s: s["num"])]
    return [r for r in dict.fromkeys(tokens) if r]

def tags():
    return set(git("tag", "-l").split())

def decide():
    exs, _ = examples()
    sls, sha, cfg = slices(), head(), config()

    def act(action, reason, **kw):
        return dict(action=action, **kw, reason=reason)

    if not sls:
        return act("idle", "no slices yet: run /skill:mismagent-specify first")
    held = open_stack_reviews()
    if held:
        return act("idle", "stack review %s is open (%s/%s-status.md): /skill:mismagent-specify finishes it"
                   % (", ".join(held), STACK_REVIEWS, held[0]))
    missing = [k for k in ("test", "lint") if not cfg.get(k)]
    if not os.path.isfile(os.path.join(ROOT, "ARCHITECTURE.md")) or missing:
        return act("skeleton", "AGENTS.md ## mismagent lacks " + " and ".join(missing) if missing
                   else "no ARCHITECTURE.md at the root")
    for s in [s for s in sls if s["state"] == "doing"][:1]:
        one = dict(slice=s["stem"], path=s["path"])
        if s["blocked"]:
            return act("blocked", "%s: the last ## Question has no ## Answer after it" % s["path"], **one)
        revs = reviews(s["stem"])
        r = at_head(revs, sha)
        directs = [x for x in revs if x["verdict"] == "DIRECT"]
        k = sum(1 for x in revs if x["verdict"] == "REWORK")
        if r:
            one["review"] = r["path"]
        if r and r["verdict"] == "PASS":
            return act("land", said(r, "is PASS at HEAD"), **one)
        if r and r["verdict"] == "DIRECT":
            return act("rework", "review %d at HEAD is the architect's DIRECT: follow it" % r["k"], k=k, **one)
        if r and r["verdict"] == "REWORK":
            if directs and r["k"] > directs[0]["k"]:
                return act("stuck", "%s after the architect's DIRECT (%s): the human decides"
                           % (said(r, "is REWORK"), ", ".join(x["path"] for x in directs)), k=k, **one)
            if k > MAX_REWORK and not directs:
                return act("escalate", "REWORK number %d (%s): the architect decides"
                           % (k, said(r, "at HEAD")), k=k, **one)
            return act("rework", "%s (round %d of %d)" % (said(r, "is REWORK at HEAD"), k, MAX_REWORK),
                       k=k, **one)
        if dirty():
            return act("resume", "uncommitted changes and no review at HEAD", **one)
        work = git("diff", "--name-only", "%s..HEAD" % s["base"], "--", ".", ":(exclude).mismagent",
                   check=False).split() if s["base"] else []
        if not work:
            return act("build", "no change outside .mismagent/ since mm start", **one)
        if not (re.search(r"^##\s+Progress\b", read(s["path"]), re.M | re.I)
                or re.search(r"^##\s+" + re.escape(s["stem"]), read(OLD_PROGRESS), re.M)):
            return act("resume", "%d file(s) changed but no '## Progress' in %s: the builder was cut"
                       % (len(work), s["path"]), **one)
        return act("review", "%d file(s) changed since mm start, progress entry written, no review at HEAD"
                   % len(work), **one)

    proposals = count_items(PROPOSALS)
    if proposals:
        return act("conventions", "%d proposal(s) in %s: the human decides them" % (proposals, PROPOSALS),
                   proposals=proposals)
    if any(s["kind"] == "model" and s["state"] == "done" for s in sls) and not os.path.isfile(
            os.path.join(ROOT, SKILL, "SKILL.md")):
        return act("conventions", "the model slice is done and there is no conventions skill yet")
    tagged = tags()
    order = release_order(exs, sls)
    for rel in order:
        mine = [s for s in sls if s["release"] == rel]
        if rel in tagged or not mine or any(s["state"] != "done" for s in mine):
            continue
        revs = reviews(rel)
        r = at_head(revs, sha)
        if not r:
            return act("release-review", "all %d slices done, no review at HEAD" % len(mine), release=rel)
        if r["verdict"] == "HEALTHY":
            return act("confirm", "release review %d is HEALTHY: the human confirms" % r["k"], release=rel)
        if r["verdict"] == "DESIGN-PASS":
            before = sum(1 for x in revs if x["verdict"] == "DESIGN-PASS" and x["k"] < r["k"])
            if before >= MAX_DESIGN_PASSES:
                return act("confirm", "DESIGN-PASS again after %d design passes: the human confirms with "
                           "the reason" % before, release=rel)
            return act("design-pass", "release " + said(r, "asks for a design pass"), release=rel)
        return act("release-review", "review %d at HEAD: no HEALTHY/DESIGN-PASS" % r["k"], release=rel)

    todo = sorted((s for s in sls if s["state"] == "todo"),
                  key=lambda s: (s["kind"] != "refactor", s["num"], s["stem"]))
    notes = count_items(NOTES)
    if notes > NOTES_LIMIT and not any(s["kind"] == "refactor" for s in todo):
        rel = next((r for r in order if r not in tagged), order[-1] if order else "")
        return act("design-pass", "%d design notes, no refactor slice in todo" % notes,
                   notes=notes, release=rel)
    waiting = {s["stem"]: waits_for(s, sls) for s in todo}
    ready = [s for s in todo if not waiting[s["stem"]]]
    if todo and not ready:
        return act("idle", "every todo slice waits (After:): " + "; ".join(
            "%s for %s" % (st, ", ".join(w)) for st, w in waiting.items()))
    todo = ready
    if todo:
        return act("start", "%s slice first in todo" % (todo[0]["kind"] or "?"),
                   slice=todo[0]["stem"], path=todo[0]["path"])
    why = "every release is tagged" if order and set(order) <= tagged else "no slice in todo"
    return act("idle", why + ": the next release needs specify")

def cmd_next(a):
    d = decide()
    if a.json:
        print(json.dumps(d))
    else:
        arg = "notes" if "notes" in d else d.get("slice") or d.get("release") or ""
        parts = [d["action"], arg, str(d["k"]) if d["action"] == "rework" else ""]
        print("%s — %s" % (" ".join(p for p in parts if p), d["reason"]))
    return 0

def cmd_status(a):
    exs, errs = examples()
    sls, marks = slices(), markers()
    known = {e["id"] for e in exs}
    per_state = {st: [s["stem"] for s in sls if s["state"] == st] for st in STATES}
    tagged = tags()
    per_release = {rel: dict({st: sum(1 for s in sls if (s["release"], s["state"]) == (rel, st))
                              for st in STATES}, tagged=rel in tagged) for rel in release_order(exs, sls)}
    data = {"slices": per_state, "releases": per_release,
            "missing_acceptance": [e["id"] for e in exs if not e["superseded"] and e["id"] not in marks],
            "superseded": [e["id"] for e in exs if e["superseded"]],
            "unknown_markers": {ex: files for ex, files in sorted(marks.items()) if ex not in known},
            "notes": count_items(NOTES), "proposals": count_items(PROPOSALS), "example_errors": errs}
    if a.json:
        print(json.dumps(data, indent=2))
        return 0
    print("slices: " + " · ".join("%s %d%s" % (st, len(v), " (%s)" % ", ".join(v) if v and st != "done"
                                                    else "") for st, v in per_state.items()))
    for rel, c in per_release.items():
        print("%s: done %d/%d%s" % (rel, c["done"], sum(c[st] for st in STATES),
                                    " (tagged)" if c["tagged"] else ""))
    print("examples without acceptance test: %s" % (", ".join(data["missing_acceptance"]) or "none"))
    print("superseded examples: %s" % (", ".join(data["superseded"]) or "none"))
    for ex, files in data["unknown_markers"].items():
        print("marker naming an unknown example: %s (%s)" % (ex, ", ".join(sorted(files))))
    print("design notes: %d · convention proposals: %d" % (data["notes"], data["proposals"]))
    report(errs, [])
    return 0

def sources():
    for rel in git("ls-files").splitlines():
        rel = rel.strip('"')
        if (os.path.splitext(rel)[1].lower() in SOURCE_EXT and not rel.startswith(M + "/")
                and os.path.isfile(os.path.join(ROOT, rel))):
            yield rel

def guarded(path):
    base = os.path.basename(path)
    return (path == OLD_EXAMPLES or path.startswith(EXAMPLES + "/") or path.startswith(SKILL + "/") or fnmatch.fnmatch(base, "REQUISITI*")
            or (fnmatch.fnmatch(base.lower(), "requirements*") and base.lower().endswith(".md")))

def run_check(base=None):
    """-> (errors, warnings)."""
    (exs, errors), warnings, marks = examples(), [], markers()
    known, retired = {e["id"] for e in exs}, {e["id"] for e in exs if e["superseded"]}
    sls = slices()
    if OLD_EXAMPLES in example_files():
        warnings.append("%s is one table for the whole product: split it by capability into %s/<capability>.md "
                        "(specify, with the human)" % (OLD_EXAMPLES, EXAMPLES))
    words = len(read(BRIEF).split())
    if words > BRIEF_WORDS:
        warnings.append("%s: %d words > %d: rewrite it as one page; decisions go to decisions/, a release's "
                        "scope and open questions to releases/<release>.md" % (BRIEF, words, BRIEF_WORDS))
    bare = sorted(os.path.basename(r) for r in walk(".mismagent/decisions")
                  if r.endswith(".md") and not re.search(r"^(#+\s*)?Evidence\b", read(r), re.M | re.I))
    if bare:  # one line, however many: a flood of these pushes the verdict out of a reader's tail
        warnings.append("%d decision(s) in .mismagent/decisions/ with no Evidence: section (every fact "
                        "carries its source): %s" % (len(bare), ", ".join(bare)))
    for s in sls:
        where = s["path"]
        if not re.fullmatch(r"\d+-.+", s["stem"]):
            errors.append("%s: name is not NN-name.md" % where)
        if s["kind"] not in KINDS:
            errors.append("%s: Kind %r is not model|feature|refactor" % (where, s["kind"]))
        if not s["release"]:
            errors.append("%s: no Release:" % where)
        errors += ["%s: Examples: %r is not EX-<n>" % (where, t) for t in s["bad_examples"]]
        errors += ["%s: After: %r names no single slice" % (where, r) for r in s["after"]
                   if not dep(r, sls) or dep(r, sls)["stem"] == s["stem"]]
        errors += ["%s: example %s is not in %s/" % (where, ex, EXAMPLES) for ex in s["examples"] if ex not in known]
        if s["state"] == "done" or (base and s["state"] == "doing"):  # in review, the tests exist
            errors += ["%s: %s, but %s has no acceptance marker under %s/" % (where, s["state"], ex, ", ".join(acceptance()))
                       for ex in unmarked(s, marks, retired) if ex in known]
        if s["state"] != "todo" and not s["base"]:
            errors.append("%s: in %s without Base:" % (where, s["state"]))
    cfg = config()
    limit, allowed = cfg_int(cfg, "max_file_lines", 400), cfg_int(cfg, "suppressions", 0)
    count = 0
    for rel in sources():
        lines = read(rel).splitlines()
        count, n = count + sum(1 for line in lines if SUPPRESS.search(line)), len(lines)
        if n > limit and not rel.startswith("tests/"):
            errors.append("%s: %d lines > max_file_lines %d" % (rel, n, limit))
    if count > allowed:
        errors.append("suppression markers: %d > suppressions %d" % (count, allowed))
    if base:
        git("rev-parse", "--verify", "--quiet", base + "^{commit}")
        doing = [s for s in sls if s["state"] == "doing"][:1]
        if doing and doing[0]["kind"] == "feature":
            allowed_ex = set(doing[0]["examples"]) | retired
            changed = git("diff", "--name-status", "-M", "--diff-filter=MR", base, "--", *acceptance())
            for line in changed.splitlines():
                st, *paths = line.split("\t")
                if st != "R100" and not set(EX_MARK.findall(read(paths[-1]))) & allowed_ex:
                    errors.append("%s: acceptance test %s since %s, naming no example of %s"
                                  % (paths[-1], "modified" if st == "M" else "renamed and edited", base,
                                     doing[0]["stem"]))
        errors += ["%s: changed since %s (the human's file: specify or conventions changes it)" % (rel, base)
                   for rel in git("diff", "--name-only", base).splitlines() if guarded(rel)]
    for rel in (r for r in walk(SKILL) if r.endswith(".md")):
        words = len(read(rel).split())
        if "/references/" in "/" + rel and words > TOPIC_WORDS:
            warnings.append("%s: %d words > %d: rewrite the topic as one rule, or split it"
                            % (rel, words, TOPIC_WORDS))
        for cited in set(CITED.findall(read(rel))):
            if ("/" in cited or os.path.splitext(cited)[1] in SOURCE_EXT) and not any(
                    os.path.exists(os.path.join(ROOT, d, cited)) for d in ("", SKILL)):
                errors.append("%s: cites %s, which does not exist (update the skill)" % (rel, cited))
    return errors, warnings

def report(errors, warnings):
    for line in ["error: " + e for e in errors] + ["warning: " + w for w in warnings]:
        print(line)

def cmd_check(a):
    errors, warnings = run_check(a.base)
    report(errors, warnings)
    need(not errors, "check: %d error(s)" % len(errors))
    print("check: ok")
    return 0

def gate():
    """Runs test, lint, check, one line each; refuses when any is red."""
    cfg, red, detail = config(), [], []
    for key in ("test", "lint"):
        cmd = cfg.get(key)
        if not cmd:
            print("%s: red (not configured in AGENTS.md ## mismagent)" % key)
            red.append(key)
            continue
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
        print("%s: %s (%s)" % (key, "green" if p.returncode == 0 else "red", cmd))
        if p.returncode:
            red.append(key)
            tail = ["  %s: %s" % (key, x) for x in (p.stdout + p.stderr).strip().splitlines()[-15:]]
            detail += tail
            for line in tail:
                print(line)
    errors, warnings = run_check()
    report(errors, warnings)
    print("check: %s" % ("red" if errors else "green"))
    if errors:
        red.append("check")
        detail += ["  check: " + e for e in errors]
    if red:  # the verdict is the last line of stdout and of stderr, whatever a `| tail` keeps
        verdict = "gate: red (%s)" % ", ".join(red)
        print(verdict)
        need(False, "\n".join(["gate red: " + ", ".join(red)] + detail + [verdict]))
    print("gate: green")

def cmd_gate(a):
    gate()
    return 0

def move(s, state):
    dest = "%s/slices/%s/%s.md" % (M, state, s["stem"])
    os.makedirs(os.path.join(ROOT, os.path.dirname(dest)), exist_ok=True)
    git("mv", s["path"], dest)
    return dest

def write_base(rel, sha):
    lines = read(rel).splitlines()
    top = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    hdr = {i: m.group(1).lower() for i, m in ((i, re.match(r"^[-*\s]*(?:\*\*)?(kind|release|examples|base)\b",
                                                          lines[i], re.I)) for i in range(top)) if m}
    base = [i for i, key in hdr.items() if key == "base"]
    if base:
        lines[base[0]] = "Base: " + sha
    else:
        lines.insert(max(hdr) + 1 if hdr else 0, "Base: " + sha)
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def cmd_start(a):
    sls = slices()
    s = find_slice(a.slice, sls)
    need(s["state"] == "todo", "%s is in %s, not todo" % (s["stem"], s["state"]))
    doing = [x["stem"] for x in sls if x["state"] == "doing"]
    need(not doing, "a slice is already in doing: %s" % ", ".join(doing))
    held = open_stack_reviews()
    need(not held, "stack review %s is open: nothing starts until it is done" % ", ".join(held))
    waits = waits_for(s, sls)
    need(not waits, "%s waits for %s (After:)" % (s["stem"], ", ".join(waits)))
    need(not dirty(), "the tree is dirty: commit or discard first")
    sha = head()
    dest = move(s, "doing")
    write_base(dest, sha)
    git("add", "--", dest)
    git("commit", "-q", "-m", "mm start %s" % s["stem"])
    print("started %s: %s (Base %s)" % (s["stem"], dest, sha[:12]))
    return 0

def cmd_park(a):
    s = find_slice(a.slice, slices())
    need(s["state"] == "doing", "%s is in %s, not doing" % (s["stem"], s["state"]))
    need(not dirty(), "the tree is dirty: commit or discard first")
    need(s["base"] and subprocess.run(["git", "rev-parse", "-q", "--verify", s["base"] + "^{commit}"],
                                      cwd=ROOT, capture_output=True).returncode == 0,
         "%s has no valid Base: (%r): its work cannot be checked" % (s["stem"], s["base"]))
    work = git("diff", "--name-only", "%s..HEAD" % s["base"], "--", ".", ":(exclude).mismagent").split()
    need(not work, "%s has work since Base (%d file(s)): finish it, or revert it first"
         % (s["stem"], len(work)))
    dest = move(s, "todo")
    lines = read(dest).splitlines()
    with open(os.path.join(ROOT, dest), "w", encoding="utf-8") as f:
        f.write("\n".join(l for l in lines if not re.match(r"^[-*\s]*(?:\*\*)?base\b", l, re.I)) + "\n")
    git("add", "--", dest)
    git("commit", "-q", "-m", "mm park %s" % s["stem"])
    print("parked %s: %s" % (s["stem"], dest))
    return 0

def cmd_land(a):
    s = find_slice(a.slice, slices())
    need(s["state"] == "doing", "%s is in %s, not doing" % (s["stem"], s["state"]))
    r = at_head(reviews(s["stem"]), head())
    need(r and r["verdict"] == "PASS", "no PASS review of %s at HEAD%s"
         % (s["stem"], " (%s)" % r["why"] if r and r["why"] else ""))
    need(not dirty(), "the tree is dirty: the PASS does not cover uncommitted changes")
    exs, _ = examples()
    missing = unmarked(s, markers(), {e["id"] for e in exs if e["superseded"]})
    need(not missing, "%s has no acceptance marker under %s/: a done slice proves its examples"
         % (", ".join(missing), ", ".join(acceptance())))
    gate()
    move(s, "done")
    extra = [p for p in (REVIEWS, NOTES) if os.path.exists(os.path.join(ROOT, p))]
    if extra:
        git("add", "-A", "--", *extra)
    git("commit", "-q", "-m", "mm land %s" % s["stem"])
    print("landed %s" % s["stem"])
    return 0

def cmd_tag(a):
    rel = a.release
    need(rel not in tags(), "%s is already tagged" % rel)
    mine = [s for s in slices() if s["release"] == rel]
    need(mine, "no slice has Release: %s" % rel)
    open_ = [s["stem"] for s in mine if s["state"] != "done"]
    need(not open_, "%s has slices not done: %s" % (rel, ", ".join(open_)))
    need(not dirty(), "the tree is dirty")
    gate()
    if os.path.isdir(os.path.join(ROOT, REVIEWS)):
        git("add", "-A", "--", REVIEWS)
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--", REVIEWS], cwd=ROOT).returncode:
            git("commit", "-q", "-m", "review: %s" % rel, "--", REVIEWS)
    git("tag", "-a", rel, "-m", "mismagent release %s" % rel)
    print("tagged %s at %s" % (rel, head()[:12]))
    return 0

SUBCOMMANDS = (  # name, help, positional argument (name, help) or a --json flag
    ("status", "slices per state and release, examples vs acceptance tests, notes", "--json"),
    ("next", "exactly one next action: <action> <arg...> — <reason>", "--json"),
    ("start", "todo -> doing, write Base:, commit (clean tree, nothing in doing)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("park", "doing -> todo, drop Base:, commit (clean tree, no work since Base)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("land", "doing -> done, commit (PASS at HEAD, clean tree, gate green)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("gate", "run test and lint from AGENTS.md ## mismagent, then check", None),
    ("tag", "git tag -a <release> (all its slices done, clean tree, gate green)",
     ("release", "release token, e.g. R0")),
    ("check", "files well formed, acceptance markers, sensors, guarded files", None))

def parser():
    p = argparse.ArgumentParser(prog="mm", description="mismAgent 0.7: slice lifecycle, git, counting.")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    for name, help_, arg in SUBCOMMANDS:
        s = sub.add_parser(name, help=help_, description=help_)
        s.set_defaults(fn=globals()["cmd_" + name])
        if arg == "--json":
            s.add_argument("--json", action="store_true", help="machine-readable output")
        elif arg:
            s.add_argument(arg[0], help=arg[1])
    sub.choices["check"].add_argument("--base", help="also refuse modified acceptance tests and "
                                      "changed requirement files since this ref")
    return p

def main(argv=None):
    global ROOT
    a = parser().parse_args(argv)
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if p.returncode:
            raise Refused("not inside a git repository")
        ROOT = p.stdout.strip()
        return a.fn(a)
    except Refused as e:
        sys.stdout.flush()  # stdout first: piped, it is buffered and would land after stderr
        print("mm: %s" % e, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
