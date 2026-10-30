#!/usr/bin/env python3
"""mm — the deterministic tool of mismAgent 0.7 (Python 3 stdlib only).

Owns ALL the git and all the counting of the slice lifecycle; no prompt carries it. Works on the
git repository containing the cwd. One lifecycle per checkout: one slice at a time in doing (code
built in another worktree is integrated here before `mm built`, the human's commits kept as they
are; two slices in doing -> `stuck`); `start` records Base, the reviewer reviews Base..HEAD, a REWORK
adds commits, nothing reaches done/ without a PASS at HEAD and a green gate. Exit: 0 ok · 1 check/gate failure or refused precondition (one
line on stderr) · 2 usage. Files, parsed line by line (forgiving about whitespace and **bold**):
  CLAUDE.md `## mismagent`: `- key: value` — test, lint, smoke, max_file_lines (400), suppressions (0),
    acceptance (tests/acceptance; comma-separated folders, for a build that wants tests elsewhere),
    shot (renders the app's screens: one $MM_SHOTS/<name>.png per name in $MM_DESIGN),
    timeout (1800: the seconds a test, lint or shot command may take; past it the command and its
    children are ended and the gate is red)
  .mismagent/examples/<capability>.md: | id | given | when | then | rule | req | release |, ids EX-<n>
    unique across the files; a `then` containing `(superseded by EX-<n>)` retires the row (no
    acceptance marker required). The old single .mismagent/examples.md is still read, with a warning
  .mismagent/brief.md: one page: decisions go to decisions/, a
    release's scope and open questions to releases/<release>.md
  .mismagent/releases/<release>.md: the release's goal and scope; its `## Open questions` empty
    (or `none`) once specified
  .mismagent/design/**: the human's approved artboards, as images (png, jpg, webp) beside any source
  .mismagent/slices/{todo,doing,done}/NN-name.md: Kind: (model|feature|fix|refactor — a refactor
    changes no behavior: one not done that declares `Behavior change:` is refused) Release: Examples: Design: Base: After: Built:,
    ## Question/Answer, ## Progress (the builder's notes) — After: lists slices (NN or stem) that
    must be done before it starts; Built: <round> is written by `mm built`, never by hand; Design:
    lists the artboards the slice's screens must look like (images under .mismagent/design/)
  .mismagent/shots/<slice-stem|release>/<artboard name>.png: the app's screens, written by `mm shot`
  .mismagent/reviews/{<slice-stem>,<release>}-<k>.md: VERDICT:, SHA: — written by `mm review`
    (it refuses when HEAD moved since the reviewer read it); "at HEAD" = SHA (>= 7 hex) is a prefix of HEAD
  .mismagent/design-notes.md: one note per `- ` line (a numbered or paragraph line is warned: it
    escapes the count), `- RISK` a wrong result outside a diff; over NOTES_LIMIT with no refactor
    ready -> `design-pass`, and after a pass that left them -> `idle` (the human decides) ·
    <acceptance>/**: markers EX-<n> (not E501)
  .mismagent/conventions-proposals.md: one proposal per `- ` line (create or update a topic;
    `- now ` = decided before the next slice starts)
  .mismagent/stack-reviews/N-status.md: `state:` open|decided|done — any not done holds `next`
    (`idle`): the stack is in question until specify's review and its handoff are finished
  .claude/skills/conventions/**.md: the project's conventions skill, written with the human in
    /mismagent:conventions; every `path` it cites must exist (a topic's: those under ## Example);
    a references/ topic is one kind of code, with ## Where, Uses, Shape, Must, Never, Example; a
    references/practices/ topic is how the work is done, with ## Must, Never
Design choices:
- Dirty tree = `git status` (which honours .gitignore) minus .mismagent/reviews/,
  .mismagent/design-notes.md and .mismagent/conventions-proposals.md (the reviewer writes them after
  the HEAD it reviewed; `mm land` commits them) and minus untracked run debris (__pycache__/, *.pyc,
  .pytest_cache/, *.db, *.sqlite*, *.log).
- Base = the HEAD `start` began from (a commit cannot carry its own SHA). A doing slice has work when
  Base..HEAD changes something outside .mismagent/; no work -> `build`. With work, a clean tree and
  no review at HEAD: `review` only if the slice's `Built:` is this round (reviews so far + 1),
  else `resume` — a builder cut before `mm built` has not finished. `mm built` runs the gate first,
  so no builder returns over a red gate.
- The verdict is the reviewer's, made by its blocking findings: no scores. The architect answers an
  escalation with VERDICT: DIRECT (-> `rework` following it) or PASS; a REWORK after a DIRECT ->
  `stuck` (human).
- A release with an open `- RISK` note is not reviewed: `design-pass` first (a risk leaves only as a
  slice). One still open after the last design pass touched the notes -> `idle`: the human decides.
- A DESIGN-PASS release review at HEAD asks for a pass unless a DESIGN-PASS review of that release
  came before it (one pass ran): then `confirm` — the human tags with `--why`, recorded as a
  decision, or asks for another pass. `tag` needs a review at HEAD.
- check --base guards REQUISITI*, requirements*.md (not requirements.txt, a dependency list),
  the examples and the conventions skill — a change made only by `specify`/`conventions` commits
  (touching no code) since Base, an ancestor of HEAD, with nothing uncommitted, is the human's; an
  edit undone later (a revert, by hand) cancels out. A modified, renamed-and-edited or deleted
  acceptance file naming none of the doing feature/fix slice's examples (nor a superseded one) is a
  warning for the reviewer, who judges it against Base. `mm built` runs the gate with the slice's
  Base, so the builder sees what the reviewer will check.
- Sensors: suppressions over tracked code files outside .mismagent/; size also skips tests/.
- No word cap on .mismagent/ as a whole: each thing has its file (a capability's examples, a
  decision, a release, a slice and its progress), so agents read the files they need, never the
  history whole; what lasts is kept current in the skill and ARCHITECTURE.md, not compacted.
- A release's spec holds together: each live example is named by a slice, each feature or fix slice
  names an example, its release file exists with no open question. `check` warns, one line a
  release; `check --release` refuses (specify closes on it); with all its slices done an example
  still in no slice holds the release (`idle`) and `tag` refuses it: promised, never built. So does
  an open question in its release file (a section opening with `none…` asks nothing; a question
  that waits for a later release is written in that release's file), and so does a missing `smoke:`
  (`skeleton` adds it: the release review runs the app). One predicate, `release_ready`, holds
  `next`, `review` and `tag` alike.
- A fix slice proves a bug with an example, like a feature; it starts before refactor slices, and
  both before the others.
- `park` puts a doing slice back in todo only while it has no work since Base (a stack change
  that must come first): half-done work never leaves doing unreviewed. A todo slice whose After:
  slices are not all done is skipped by `next`; when every todo slice waits -> `idle`.
- Look is proven like behavior: a slice with Design: is built only with a screen per artboard,
  rendered by the project's `shot` command at that commit (`mm built` runs it and commits them), so
  the reviewer judges the pair, never the diff alone; a release's pairs are rendered by `mm shot`.
- The conventions skill is a catalog of kinds of code and practices. A topic that is neither (its
  sections missing), or a done model slice with no skill and no proposal -> `catalog` (the architect
  proposes the whole catalog as `- now ` lines) before anything else, even a slice in doing: the gate
  stays red until it lands; once proposed -> `conventions`.
- Agents only propose conventions. A done model slice and no skill yet -> `conventions` before the
  next slice starts, and so does a `- now ` proposal (a stack migration's transition); the others
  ride on `start` (`proposals`: the human is told, the flow
  goes on) and -> `conventions` only when no slice can start or before a release is reviewed.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

KINDS = ("model", "feature", "fix", "refactor")
PROVING = ("feature", "fix")  # a slice of these kinds proves examples: it names at least one
STATES = ("todo", "doing", "done")
M = ".mismagent"
EXAMPLES, OLD_EXAMPLES, BRIEF = M + "/examples", M + "/examples.md", M + "/brief.md"
RELEASES = M + "/releases"
DESIGN, SHOTS = M + "/design", M + "/shots"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
NOTES, REVIEWS = M + "/design-notes.md", M + "/reviews"
TOPIC_SECTIONS = ("Where", "Uses", "Shape", "Must", "Never", "Example")  # a topic is one kind of code
PRACTICE_SECTIONS = ("Must", "Never")  # references/practices/: how the work is done here
SKILL, PROPOSALS = ".claude/skills/conventions", M + "/conventions-proposals.md"
STACK_REVIEWS = M + "/stack-reviews"
CITED = re.compile(r"`([\w.\-/]+)`")
IGNORED_DIRTY = (REVIEWS + "/", NOTES, PROPOSALS, SHOTS + "/")
DEBRIS = re.compile(r"(^|/)(__pycache__|\.pytest_cache)/|\.pyc$|\.db$|\.sqlite[^/]*$|\.log$")
EX_ID = re.compile(r"^EX-\d+$")
EX_MARK = re.compile(r"(?<![\w-])EX-\d+(?!\d)")
SUPERSEDED = re.compile(r"\(\s*superseded\s+by\s+EX-\d+\s*\)", re.I)
BEHAVIOR_CHANGE = re.compile(r"^[-*\s]*(?:\*\*)?behaviou?r change(?:\*\*)?\s*:", re.M | re.I)
SUPPRESS = re.compile(r"noqa|pylint:\s*disable|eslint-disable|@SuppressWarnings|type:\s*ignore|nolint")
SOURCE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
              ".kts", ".rb", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".swift", ".php", ".scala",
              ".vue", ".svelte", ".dart", ".ex", ".exs", ".lua", ".sh", ".m", ".fs", ".clj"}
MAX_REWORK, MAX_DESIGN_PASSES, NOTES_LIMIT = 2, 1, 5
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
    for line in read("CLAUDE.md").splitlines():
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
         "examples": [], "bad_examples": [], "design": [], "base": "", "after": [], "built": 0}
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
        hm = re.match(r"^(kind|release|examples|design|base|after|built)\s*:\s*(.*)$", st.lstrip("-* ").replace("**", ""), re.I)
        if hm:
            key, val = hm.group(1).lower(), hm.group(2).strip()
            if key == "examples":
                toks = [t for t in re.split(r"[,\s]+", val) if t and t not in ("-", "—", "none")]
                s["examples"] = [t for t in toks if EX_ID.match(t)]
                s["bad_examples"] = [t for t in toks if not EX_ID.match(t)]
            elif key == "design":
                s["design"] = [t for t in re.split(r"[,\s]+", val) if t and t not in ("-", "—", "none")]
            elif key == "after":
                s["after"] = [t for t in re.split(r"[,\s]+", val) if t and t not in ("-", "—", "none")]
            elif key == "built":
                s["built"] = int(val) if val.isdigit() else 0
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
    """-> [{k, verdict, sha, path}] of <prefix>-<k>.md sorted by k."""
    out = []
    for name in ls(REVIEWS):
        m = re.fullmatch(re.escape(prefix) + r"-(\d+)\.md", name)
        if not m:
            continue
        path = "%s/%s" % (REVIEWS, name)
        text = read(path)
        v = re.search(r"^[\s*_>-]*VERDICT[\s*_]*:[\s*_]*([A-Za-z-]+)", text, re.M | re.I)
        sha = re.search(r"^[\s*_>-]*SHA[\s*_]*:[\s*_`]*([0-9a-fA-F]+)", text, re.M | re.I)
        out.append({"k": int(m.group(1)), "verdict": v.group(1).upper() if v else "", "path": path,
                    "sha": sha.group(1).lower() if sha else ""})
    return sorted(out, key=lambda r: r["k"])

def at_head(revs, sha):
    hits = [r for r in revs if len(r["sha"]) >= 7 and sha.startswith(r["sha"])]
    return hits[-1] if hits else None

def said(r, text):
    return "review %d %s" % (r["k"], text)

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
    """The acceptance folders: CLAUDE.md `acceptance:` (comma-separated), else tests/acceptance."""
    folders = (d.strip().strip("`").strip().strip("/") for d in config().get("acceptance", "").split(","))
    return [d for d in folders if d] or ["tests/acceptance"]

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

def artboard(ref):
    """The repo path of a Design: reference (from the root, or from .mismagent/design/)."""
    ref = ref.strip("`")
    return ref if ref.startswith(DESIGN + "/") else "%s/%s" % (DESIGN, ref)

def design_errors(s):
    """Each Design: reference must be an image under .mismagent/design/, there to be read."""
    out = []
    for ref in s["design"]:
        rel = artboard(ref)
        if "://" in ref:
            out.append("%s: Design: %s is a link: the artboard is read from the repository — export it "
                       "as an image into %s/ (specify)" % (s["path"], ref, DESIGN))
        elif not rel.lower().endswith(IMAGE_EXT):
            out.append("%s: Design: %s is not an image (%s): export the artboard as one" % (
                s["path"], ref, " ".join(IMAGE_EXT)))
        elif ".." in rel.split("/") or not os.path.isfile(os.path.join(ROOT, rel)):
            out.append("%s: Design: %s does not exist under %s/" % (s["path"], ref, DESIGN))
    return out

def seconds(cfg):
    """`timeout:` of CLAUDE.md ## mismagent: the most a test, lint or shot command may take."""
    v = cfg.get("timeout", "")
    return int(v) if v.isdigit() and int(v) > 0 else 1800

def run(cmd, env=None):
    """Runs a project command in a process group of its own; -> (returncode, output, timed out).
    Past the timeout the whole group is ended (TERM, then KILL): a hung child never holds the flow."""
    p = subprocess.Popen(cmd, shell=True, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=seconds(config()))
        return p.returncode, out, False
    except subprocess.TimeoutExpired:
        out = ""
    except KeyboardInterrupt:  # the human cut mm: its group goes with it
        end(p, signal.SIGKILL)
        raise
    for sig in (signal.SIGTERM, signal.SIGKILL):  # KILL after TERM whatever happened: a child ignoring TERM dies too
        end(p, sig)
        try:
            out, _ = p.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    return 1, out, True

def end(p, sig):
    try:
        os.killpg(p.pid, sig)
    except ProcessLookupError:
        pass

def timed_out(key):
    return "%s: red (timed out after %d s: `timeout:` in CLAUDE.md ## mismagent)" % (key, seconds(config()))

def shoot(stem, refs):
    """Runs the project's `shot` into .mismagent/shots/<stem>/ for these artboards; -> the dir.
    Rendered apart and promoted whole: a red or cut run leaves no partial set looking current."""
    cmd = config().get("shot")
    need(cmd, "no `shot` in CLAUDE.md ## mismagent: a screen per artboard is how the look is proven "
         "(a command that writes $MM_SHOTS/<name>.png for each name in $MM_DESIGN)")
    names = [os.path.splitext(os.path.basename(artboard(r)))[0] for r in refs]
    out = "%s/%s" % (SHOTS, stem)
    tmp = os.path.join(ROOT, out + ".rendering")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    env = dict(os.environ, MM_SHOTS=tmp, MM_DESIGN=" ".join(names))
    code, output, late = run(cmd, env)
    try:
        need(not late, timed_out("shot"))
        need(code == 0, "shot: red (%s)\n%s" % (cmd, "\n".join(output.strip().splitlines()[-10:])))
        missing = [n for n in names if not os.path.isfile(os.path.join(tmp, n + ".png"))]
        need(not missing, "shot wrote no %s in %s/" % (", ".join(n + ".png" for n in missing), out))
    except Refused:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(os.path.join(ROOT, out), ignore_errors=True)
    os.rename(tmp, os.path.join(ROOT, out))
    for ref, n in zip(refs, names):
        print("%s  <->  %s/%s.png" % (artboard(ref), out, n))
    return out

def count_items(rel):
    return sum(1 for line in read(rel).splitlines() if line.lstrip().startswith("- "))

def release_order(exs, sls):
    tokens = [e["release"] for e in exs] + [s["release"] for s in sorted(sls, key=lambda s: s["num"])]
    return [r for r in dict.fromkeys(tokens) if r]

def spec_problems(rel, exs, sls):
    """What does not hold together in a release's spec: its examples, its slices, its release file."""
    mine = [s for s in sls if s["release"] == rel]
    out = ["%s is in no slice" % ex for ex in uncovered(rel, exs, sls)]
    out += ["%s: a %s slice names no example" % (s["path"], s["kind"]) for s in mine
            if s["kind"] in PROVING and not s["examples"]]
    path = "%s/%s.md" % (RELEASES, rel)
    if not os.path.isfile(os.path.join(ROOT, path)):
        out.append("no %s (the release's goal, scope and open questions)" % path)
    elif open_questions(rel):
        out.append("%s: %d open question line(s) under ## Open questions" % (path, len(open_questions(rel))))
    return out

def open_questions(rel):
    """The lines under ## Open questions of releases/<rel>.md that still ask something: none when the
    section is empty or opens with `none` (`None. Answered 2026-10-29: …` asks nothing)."""
    body = next((v for k, v in sections(read("%s/%s.md" % (RELEASES, rel))).items()
                 if k.strip().lower() == "open questions"), "")
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    if lines and lines[0].strip("-*_ ").lower().startswith("none"):  # its paragraph asks nothing; a list after it does
        while lines and not re.match(r"([-*]|\d+\.)\s", lines[0]):
            lines.pop(0)
    lines = [l.strip("-*_ ") for l in lines]
    return [l for l in lines if l and l.lower() not in ("none", "(none)", "—")]

def release_ready(rel, exs, sls, cfg):
    """What still holds release rel before its review and its tag, in order: [(what, why)] — `slices`
    not done, `examples` in no slice, `questions` open in its file, `proposals` pending, `smoke`
    missing, `risk` noted. Empty: ready for its review. One predicate for `next`, `review` and `tag`."""
    out = []
    open_ = [s["stem"] for s in sls if s["release"] == rel and s["state"] != "done"]
    if open_:
        out.append(("slices", "slices not done: %s" % ", ".join(open_)))
    missing = uncovered(rel, exs, sls)
    if missing:
        out.append(("examples", "%s in no slice: specify gives them a slice, or supersedes them" % ", ".join(missing)))
    asked = open_questions(rel)
    if asked:
        out.append(("questions", "%d open question(s) in %s/%s.md: /mismagent:specify %s answers them, or writes "
                    "one in the release it waits for" % (len(asked), RELEASES, rel, rel)))
    n = count_items(PROPOSALS)
    if n:
        out.append(("proposals", "%d proposal(s) in %s: the human decides them" % (n, PROPOSALS)))
    if not cfg.get("smoke"):
        out.append(("smoke", "no smoke: in CLAUDE.md ## mismagent: the release review runs the app through it"))
    risks = [line for line in read(NOTES).splitlines() if line.lstrip().startswith("- RISK")]
    if risks:
        out.append(("risk", "%d RISK note(s) in %s" % (len(risks), NOTES)))
    return out

def uncovered(rel, exs, sls):
    """The release's live examples that no slice names: behavior promised and never built."""
    named = {ex for s in sls for ex in s["examples"]}
    return [e["id"] for e in exs if e["release"] == rel and not e["superseded"] and e["id"] not in named]

def passed_since_notes():
    """True when a design pass committed since the design notes last changed (or was that change)."""
    last = git("log", "-1", "--format=%H", "--", NOTES, check=False).strip()
    if not last:
        return False
    subjects = git("log", "--format=%s", "%s..HEAD" % last, check=False).splitlines()
    subjects.append(git("log", "-1", "--format=%s", last, check=False).strip())
    return any(x.startswith("design pass") for x in subjects)

def tags():
    return set(git("tag", "-l").split())

def decide():
    exs, _ = examples()
    sls, sha, cfg = slices(), head(), config()

    def act(action, reason, **kw):
        return dict(action=action, **kw, reason=reason)

    if not sls:
        return act("idle", "no slices yet: run /mismagent:specify first")
    held = open_stack_reviews()
    if held:
        return act("idle", "stack review %s is open (%s/%s-status.md): /mismagent:specify finishes it"
                   % (", ".join(held), STACK_REVIEWS, held[0]))
    missing = [k for k in ("test", "lint") if not cfg.get(k)]
    if not os.path.isfile(os.path.join(ROOT, "ARCHITECTURE.md")) or missing:
        return act("skeleton", "CLAUDE.md ## mismagent lacks " + " and ".join(missing) if missing
                   else "no ARCHITECTURE.md at the root")
    proposals = count_items(PROPOSALS)
    urgent = sum(1 for line in read(PROPOSALS).splitlines() if line.lstrip().startswith("- now "))

    def decide_them():
        return act("conventions", "%d proposal(s) in %s: the human decides them" % (proposals, PROPOSALS),
                   proposals=proposals)
    has_skill = os.path.isfile(os.path.join(ROOT, SKILL, "SKILL.md"))
    model_done = any(s["kind"] == "model" and s["state"] == "done" for s in sls)
    old = old_topics()
    if old or (model_done and not has_skill and not proposals):  # the gate is red until the catalog lands
        if urgent:
            return decide_them()
        return act("catalog", "%d convention topic(s) are not a kind of code or a practice (%s) — `MM next --json` "
                   "lists them all as `topics`; the others stay"
                   % (len(old), ", ".join(os.path.basename(r) for r in old[:5]) + (", …" if len(old) > 5 else ""))
                   if old else "the model slice is done, no conventions skill and no proposal for it", topics=old)
    doing = [s for s in sls if s["state"] == "doing"]
    if len(doing) > 1:
        return act("stuck", two_doing(doing))
    for s in doing:
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
        if s["built"] != len(revs) + 1:
            return act("resume", "%d file(s) changed but no `Built: %d` in %s: the builder was cut before "
                       "mm built" % (len(work), len(revs) + 1, s["path"]), **one)
        return act("review", "%d file(s) changed since mm start, built (round %d), no review at HEAD"
                   % (len(work), s["built"]), **one)

    if model_done and not has_skill:
        return act("conventions", "the model slice is done and there is no conventions skill yet")
    if urgent:
        return decide_them()
    tagged = tags()
    order = release_order(exs, sls)
    for rel in order:
        mine = [s for s in sls if s["release"] == rel]
        if rel in tagged or not mine or any(s["state"] != "done" for s in mine):
            continue
        for what, why in release_ready(rel, exs, sls, cfg)[:1]:
            if what == "proposals":  # a release is reviewed against the conventions as decided
                return decide_them()
            if what == "smoke":
                return act("skeleton", "release %s: %s" % (rel, why), release=rel)
            if what == "risk":  # a known wrong result is fixed or ruled out before the release is judged
                if passed_since_notes():
                    return act("idle", "release %s: %s still after the design pass: the human decides — a slice "
                               "for it, or the note removed with why in .mismagent/decisions/" % (rel, why), release=rel)
                return act("design-pass", "release %s: %s: a risk leaves only as a slice" % (rel, why), release=rel)
            return act("idle", "release %s: %s" % (rel, why), release=rel)
        revs = reviews(rel)
        r = at_head(revs, sha)
        if not r:
            return act("release-review", "all %d slices done, no review at HEAD" % len(mine), release=rel)
        if r["verdict"] == "HEALTHY":
            return act("confirm", "release review %d is HEALTHY: the human confirms" % r["k"], release=rel)
        if r["verdict"] == "DESIGN-PASS":
            before = sum(1 for x in revs if x["verdict"] == "DESIGN-PASS" and x["k"] < r["k"])
            if before >= MAX_DESIGN_PASSES:
                return act("confirm", "DESIGN-PASS again after %d design pass%s: the human confirms with "
                           "`--why`, or asks for another pass" % (before, "" if before == 1 else "es"), release=rel)
            return act("design-pass", "release " + said(r, "asks for a design pass"), release=rel)
        return act("release-review", "review %d at HEAD: no HEALTHY/DESIGN-PASS" % r["k"], release=rel)

    todo = sorted((s for s in sls if s["state"] == "todo"),
                  key=lambda s: (("fix", "refactor").index(s["kind"]) if s["kind"] in ("fix", "refactor") else 2,
                                 s["num"], s["stem"]))
    notes = count_items(NOTES)
    waiting = {s["stem"]: waits_for(s, sls) for s in todo}
    ready = [s for s in todo if not waiting[s["stem"]]]
    # only a refactor slice that can start now pays the notes down; one waiting (After:) holds nothing
    if notes > NOTES_LIMIT and not any(s["kind"] == "refactor" for s in ready):
        rel = next((r for r in order if r not in tagged), order[-1] if order else "")
        if passed_since_notes():  # a pass left them where they were: another would too
            return act("idle", "%d design notes after the design pass (limit %d): the human decides — slices, "
                       "a question in a release file, or notes dropped" % (notes, NOTES_LIMIT), notes=notes, release=rel)
        return act("design-pass", "%d design notes, no refactor slice ready in todo" % notes,
                   notes=notes, release=rel)
    if proposals and not ready:
        return decide_them()
    if todo and not ready:
        return act("idle", "every todo slice waits (After:): " + "; ".join(
            "%s for %s" % (st, ", ".join(w)) for st, w in waiting.items()))
    todo = ready
    if todo:
        return act("start", "%s slice first in todo" % (todo[0]["kind"] or "?"),
                   slice=todo[0]["stem"], path=todo[0]["path"], **({"proposals": proposals} if proposals else {}))
    why = "every release is tagged" if order and set(order) <= tagged else "no slice in todo"
    return act("idle", why + ": the next release needs specify")

def two_doing(doing):
    return ("two slices in doing: %s — one checkout holds one slice: land or park the other in its own checkout "
            "(park refuses one with work)" % ", ".join(s["stem"] for s in doing))

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
    return (path == OLD_EXAMPLES or path.startswith(EXAMPLES + "/") or path.startswith(DESIGN + "/")
            or path.startswith(SKILL + "/") or fnmatch.fnmatch(base, "REQUISITI*")
            or (fnmatch.fnmatch(base.lower(), "requirements*") and base.lower().endswith(".md")))

# the subjects specify and conventions commit with (a real revert of one too); never a lookalike
HUMAN_COMMIT = re.compile(r'^(Revert "(?=.*"$))?(specify|conventions)([ :(]|$)')

def human_commit(sha):
    """A specify/conventions commit that touches only the human's files, .mismagent/ and ARCHITECTURE.md."""
    subject, *files = git("show", "--name-only", "--format=%s", sha).strip().splitlines()
    return bool(HUMAN_COMMIT.match(subject)) and all(
        guarded(f) or f.startswith(M + "/") or f == "ARCHITECTURE.md" for f in files if f)

def ancestor(base):
    return not subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=ROOT,
                              capture_output=True).returncode

def blob(sha, names):
    """The mode and blob id (`100644 <id>`) of the file at sha under the first of these names it has
    there, or None when absent under all of them."""
    for name in names:
        line = git("ls-tree", sha, "--", name, check=False).split()
        if line:
            return "%s %s" % (line[0], line[2])
    return None

def not_the_humans(paths, base):
    """-> the commits since base (an ancestor of HEAD) that changed this human's file and are not the
    human's, as `<sha7> <subject>`; the file is followed under every name it had on the way. An edit
    undone later (git revert, or by hand) cancels out: back at a state it already had, the excursion
    drops. Anything staged, unstaged or untracked is `uncommitted`; a base that is no ancestor
    exempts nothing; a merge that changed it is a commit like any other, named if not the human's."""
    if not ancestor(base):
        return ["%s is not an ancestor of HEAD" % base[:12]]
    if git("status", "--porcelain", "--untracked-files=all", "--", *paths, check=False).strip():
        return ["uncommitted changes"]
    names = list(paths)
    for p in paths:  # the names in between, so an edit under one of them hides nothing
        names += [l.strip() for l in git("log", "--follow", "--format=", "--name-only", "%s..HEAD" % base, "--", p,
                                        check=False).splitlines() if l.strip() and l.strip() not in names]
    shas = git("log", "--full-history", "--reverse", "--format=%H", "%s..HEAD" % base, "--", *names,
               check=False).split()
    stack = [(blob(base, names), None)]  # (state, the commit that set it); None = base
    for sha in shas:
        b = blob(sha, names)
        if b == stack[-1][0]:
            continue
        if b in (x[0] for x in stack):  # back to an earlier state: the excursion cancels
            while stack[-1][0] != b:
                stack.pop()
        else:
            stack.append((b, sha))
    carriers = {sha for _, sha in stack if sha}  # the commits that still account for the state at HEAD
    return ["%s %s" % (x[:7], git("log", "-1", "--format=%s", x).strip()) for x in shas
            if x in carriers and not human_commit(x)]

def run_check(base=None, release=None):
    """-> (errors, warnings); with a release, what does not hold together in its spec is an error."""
    (exs, errors), warnings, marks = examples(), [], markers()
    known, retired = {e["id"] for e in exs}, {e["id"] for e in exs if e["superseded"]}
    sls = slices()
    if OLD_EXAMPLES in example_files():
        warnings.append("%s is one table for the whole product: split it by capability into %s/<capability>.md "
                        "(specify, with the human)" % (OLD_EXAMPLES, EXAMPLES))
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
            errors.append("%s: Kind %r is not %s" % (where, s["kind"], "|".join(KINDS)))
        if not s["release"]:
            errors.append("%s: no Release:" % where)
        errors += ["%s: Examples: %r is not EX-<n>" % (where, t) for t in s["bad_examples"]]
        errors += ["%s: After: %r names no single slice" % (where, r) for r in s["after"]
                   if not dep(r, sls) or dep(r, sls)["stem"] == s["stem"]]
        errors += ["%s: example %s is not in %s/" % (where, ex, EXAMPLES) for ex in s["examples"] if ex not in known]
        errors += design_errors(s)
        if s["kind"] == "refactor" and s["state"] != "done" and BEHAVIOR_CHANGE.search(read(s["path"])):
            errors.append("%s: a refactor changes no behavior: the change is a fix or a feature with an example "
                          "(a ## Question for specify), or is reverted" % where)
        if s["state"] == "done" or (base and s["state"] == "doing"):  # in review, the tests exist
            errors += ["%s: %s, but %s has no acceptance marker under %s/" % (where, s["state"], ex, ", ".join(acceptance()))
                       for ex in unmarked(s, marks, retired) if ex in known]
        if s["state"] != "todo" and not s["base"]:
            errors.append("%s: in %s without Base:" % (where, s["state"]))
    tagged = tags()
    for rel in release_order(exs, sls):
        problems = spec_problems(rel, exs, sls)
        if rel == release:
            errors += ["%s: %s" % (rel, p) for p in problems]
        elif problems and rel not in tagged:  # one line a release: the gate's verdict stays in view
            warnings.append("%s: %s (mm check --release %s)" % (rel, "; ".join(problems), rel))
    if release and release not in release_order(exs, sls):
        errors.append("%s: no example and no slice names this release" % release)
    cfg = config()
    if "timeout" in cfg and not (cfg["timeout"].isdigit() and int(cfg["timeout"]) > 0):
        errors.append("CLAUDE.md ## mismagent: timeout: %r is not a positive number of seconds" % cfg["timeout"])
    if not cfg.get("smoke"):
        warnings.append("CLAUDE.md ## mismagent: no smoke: — the release review runs the app through it; mm asks "
                        "for the skeleton before the review")
    prose = [l for l in read(NOTES).splitlines() if l.strip() and not l.startswith(("- ", "#", " ", "\t"))]
    if prose:  # numbered or paragraph notes escape the count that calls the design pass
        warnings.append("%s: %d line(s) that are not notes (a note is one `- ` line; headings, blank and indented "
                        "lines are fine), from %r" % (NOTES, len(prose), prose[0][:40]))
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
        if doing and doing[0]["kind"] in PROVING:  # another example's test touched: the reviewer judges it
            allowed_ex = set(doing[0]["examples"]) | retired
            changed = git("diff", "--name-status", "-M", "--diff-filter=MRD", base, "--", *acceptance())
            for line in changed.splitlines():
                st, *paths = line.split("\t")
                if st != "R100" and not set(EX_MARK.findall(read(paths[-1]))) & allowed_ex:
                    warnings.append("%s: acceptance file %s since %s, naming no example of %s: the reviewer "
                                    "judges it against `git show %s:%s`"
                                    % (paths[-1], {"M": "modified", "D": "deleted"}.get(st[0], "renamed and edited"),
                                       base, doing[0]["stem"], base[:12], paths[0]))
        for line in git("diff", "--name-status", "-M", base).splitlines():
            paths = line.split("\t")[1:]
            if any(guarded(x) for x in paths):
                others = not_the_humans(paths, base)
                if others:
                    errors.append("%s: changed since %s by %s (the human's file: specify or conventions "
                                  "changes it)" % (paths[-1], base, "; ".join(others)))
    for rel in (r for r in walk(SKILL) if r.endswith(".md")):
        text, practice = read(rel), "/references/practices/" in "/" + rel
        if "/references/" in "/" + rel:
            missing, need = topic_missing(rel), PRACTICE_SECTIONS if practice else TOPIC_SECTIONS
            if missing:
                errors.append("%s: no ## %s (a %s has ## %s)" % (rel, ", ## ".join(missing),
                              "practice" if practice else "kind of code", ", ## ".join(need)))
            if not practice:  # Where names folders to come: only Example cites files that must exist
                text = sections(text).get("Example", "")
        for cited in set(CITED.findall(text)):
            if ("/" in cited or os.path.splitext(cited)[1] in SOURCE_EXT) and not any(
                    os.path.exists(os.path.join(ROOT, d, cited)) for d in ("", SKILL)):
                errors.append("%s: cites %s, which does not exist (update the skill)" % (rel, cited))
    return errors, warnings

def topic_missing(rel):
    """The sections a topic of the conventions skill lacks: a kind of code, or a practice."""
    secs = sections(read(rel))
    need = PRACTICE_SECTIONS if "/references/practices/" in "/" + rel else TOPIC_SECTIONS
    return [s for s in need if s not in secs]

def old_topics():
    return [r for r in walk(SKILL) if r.endswith(".md") and "/references/" in "/" + r and topic_missing(r)]

def sections(text):
    """{title: body} of the `## ` headings of a Markdown text, outside fenced code."""
    secs, title, fence = {}, None, None
    for line in text.splitlines():
        m = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if m:
            fence = None if fence and m.group(1)[0] == fence else (fence or m.group(1)[0])
        h = None if fence else re.match(r" {0,3}##[ \t]+(.+?)[ \t]*#*[ \t]*$", line)
        if h:
            title = h.group(1)
            secs.setdefault(title, "")
        elif title:
            secs[title] += line + "\n"
    return secs

def report(errors, warnings):
    for line in ["error: " + e for e in errors] + ["warning: " + w for w in warnings]:
        print(line)

def cmd_check(a):
    errors, warnings = run_check(a.base, a.release)
    report(errors, warnings)
    need(not errors, "check: %d error(s)" % len(errors))
    print("check: ok")
    return 0

def gate(base=None):
    """Runs check (with base: the slice's files too), then test and lint, one line each; refuses when
    any is red. Check first: it is cheap, and a red one is not worth a suite run."""
    cfg, red, detail = config(), [], []
    errors, warnings = run_check(base)
    report(errors, warnings)
    print("check: %s" % ("red" if errors else "green"))
    if errors:
        red.append("check")
        detail += ["  check: " + e for e in errors]
    for key in ("test", "lint"):
        cmd = cfg.get(key)
        if not cmd:
            print("%s: red (not configured in CLAUDE.md ## mismagent)" % key)
            red.append(key)
            continue
        if errors:
            print("%s: not run (check red)" % key)
            continue
        code, out, late = run(cmd)
        print(timed_out(key) if late else "%s: %s (%s)" % (key, "green" if code == 0 else "red", cmd))
        if code:
            red.append(key)
            tail = ["  %s: %s" % (key, x) for x in out.strip().splitlines()[-15:]]
            detail += tail
            for line in tail:
                print(line)
    if not red:  # the commands ran: the tree they left is the one check certifies
        errors, _ = run_check(base)
        if errors:
            report(errors, [])
            print("check: red (after the commands)")
            red.append("check")
            detail += ["  check: " + e for e in errors]
    if red:  # the verdict is the last line of stdout and of stderr, whatever a `| tail` keeps
        verdict = "gate: red (%s)" % ", ".join(red)
        print(verdict)
        need(False, "\n".join(["gate red: " + ", ".join(red)] + detail + [verdict]))
    print("gate: green")

def cmd_gate(a):
    gate(a.base)
    return 0

def move(s, state):
    dest = "%s/slices/%s/%s.md" % (M, state, s["stem"])
    os.makedirs(os.path.join(ROOT, os.path.dirname(dest)), exist_ok=True)
    git("mv", s["path"], dest)
    return dest

def drop_drafts():
    """Review drafts are working files: removed before land and tag commit reviews/."""
    for rel in [r for r in walk(REVIEWS) if r.endswith(".draft.md")]:
        os.remove(os.path.join(ROOT, rel))

def write_header(rel, key, value):
    """Sets the header line `<Key>: <value>` of a slice file, after the other header lines."""
    lines = read(rel).splitlines()
    top = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    hdr = {i: m.group(1).lower() for i, m in ((i, re.match(r"^[-*\s]*(?:\*\*)?(kind|release|examples|base|after|built)(?:\*\*)?\s*:",
                                                          lines[i], re.I)) for i in range(top)) if m}
    mine = [i for i, k in hdr.items() if k == key.lower()]
    if mine:
        lines[mine[0]] = "%s: %s" % (key, value)
    else:
        lines.insert(max(hdr) + 1 if hdr else 0, "%s: %s" % (key, value))
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
    write_header(dest, "Base", sha)
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
        f.write("\n".join(l for l in lines if not re.match(r"^[-*\s]*(?:\*\*)?base(?:\*\*)?\s*:", l, re.I)) + "\n")
    git("add", "--", dest)
    git("commit", "-q", "-m", "mm park %s" % s["stem"])
    print("parked %s: %s" % (s["stem"], dest))
    return 0

def cmd_built(a):
    sls = slices()
    s = find_slice(a.slice, sls)
    need(s["state"] == "doing", "%s is in %s, not doing" % (s["stem"], s["state"]))
    doing = [x for x in sls if x["state"] == "doing"]
    need(len(doing) == 1, two_doing(doing))
    need(not dirty(), "the tree is dirty: commit your work first")
    work = git("diff", "--name-only", "%s..HEAD" % s["base"], "--", ".", ":(exclude).mismagent",
               check=False).split() if s["base"] else []
    need(work, "nothing built since mm start (no change outside .mismagent/ since Base)")
    need(ancestor(s["base"]), "%s: Base %s is not an ancestor of HEAD: its work cannot be checked"
         % (s["stem"], s["base"][:12]))
    revs = reviews(s["stem"])
    r = at_head(revs, head())
    need(not r, "review %d is at HEAD: nothing changed since it" % (r or {"k": 0})["k"])
    gate(s["base"])  # what the reviewer will check: the builder sees it first
    errs = design_errors(s)
    need(not errs, "; ".join(errs))
    shots = [shoot(s["stem"], s["design"])] if s["design"] else []
    rnd = len(revs) + 1
    write_header(s["path"], "Built", rnd)
    git("add", "-A", "--", s["path"], *shots)
    git("commit", "-q", "--allow-empty", "-m", "%s: built (round %d)" % (s["stem"], rnd))  # again in a round: same header
    print("built %s, round %d: ready for review" % (s["stem"], rnd))
    return 0

def cmd_shot(a):
    sls = slices()
    try:
        mine = [find_slice(a.target, sls)]
        target = mine[0]["stem"]
    except Refused:
        mine, target = [s for s in sls if s["release"] == a.target], a.target
        need(mine, "%s is neither a slice nor a release" % a.target)
    errs = [e for s in mine for e in design_errors(s)]
    need(not errs, "; ".join(errs))
    refs = list(dict.fromkeys(r for s in mine for r in s["design"]))
    need(refs, "%s names no artboard (Design:)" % target)
    shoot(target, refs)
    return 0

def cmd_review(a):
    v, sls = a.verdict.upper(), slices()
    try:
        mine = find_slice(a.target, sls)
    except Refused:
        mine = None
    if mine:
        need(mine["state"] == "doing", "%s is in %s, not doing" % (mine["stem"], mine["state"]))
        target, allowed = mine["stem"], ("PASS", "REWORK", "DIRECT")
    else:
        need(any(x["release"] == a.target for x in sls), "%s is neither a slice nor a release" % a.target)
        # a risk or a proposal this review wrote is its output, never what refuses it
        holds = [h for h in release_ready(a.target, examples()[0], sls, config()) if h[0] not in ("risk", "proposals")]
        need(not holds, "%s: not ready for a release review: %s" % (a.target, holds[0][1] if holds else ""))
        target, allowed = a.target, ("HEALTHY", "DESIGN-PASS")
    need(v in allowed, "verdict %s: %s takes %s" % (v, target, " | ".join(allowed)))
    sha = head()
    need(len(a.sha) >= 7 and sha.startswith(a.sha.lower()),
         "HEAD moved since you read it (%s, now %s): review again what is there now" % (a.sha, sha[:12]))
    need(not dirty(), "the tree is dirty: a review covers committed code only")
    draft = os.path.join(ROOT, REVIEWS, "%s.draft.md" % target)  # under reviews/: it leaves the tree clean
    src = a.body or draft  # --body is the caller's path, relative to where mm runs
    try:
        with open(src, encoding="utf-8") as f:
            body = f.read()
    except (OSError, UnicodeDecodeError):
        body = ""
    need(body.strip(), "%s is missing or empty: the checklist and the findings go there"
         % (a.body or os.path.relpath(draft, ROOT)))
    if not a.body:  # a draft left by an earlier, refused attempt is not this review
        need(os.path.getmtime(draft) >= int(git("log", "-1", "--format=%ct").strip()),
             "%s was written before HEAD: write the review of the code at HEAD" % os.path.relpath(draft, ROOT))
    k = max((r["k"] for r in reviews(target)), default=0) + 1
    rel = "%s/%s-%d.md" % (REVIEWS, target, k)
    os.makedirs(os.path.join(ROOT, REVIEWS), exist_ok=True)
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
        f.write("VERDICT: %s\nSHA: %s\n\n%s\n" % (v, sha, body.strip()))
    if not a.body:
        os.remove(draft)
    print(rel)
    return 0

def cmd_land(a):
    sls = slices()
    s = find_slice(a.slice, sls)
    need(s["state"] == "doing", "%s is in %s, not doing" % (s["stem"], s["state"]))
    doing = [x for x in sls if x["state"] == "doing"]
    need(len(doing) == 1, two_doing(doing))
    r = at_head(reviews(s["stem"]), head())
    need(r and r["verdict"] == "PASS", "no PASS review of %s at HEAD" % s["stem"])
    need(not dirty(), "the tree is dirty: the PASS does not cover uncommitted changes")
    exs, _ = examples()
    missing = unmarked(s, markers(), {e["id"] for e in exs if e["superseded"]})
    need(not missing, "%s has no acceptance marker under %s/: a done slice proves its examples"
         % (", ".join(missing), ", ".join(acceptance())))
    gate()
    move(s, "done")
    drop_drafts()
    extra = [p for p in (REVIEWS, NOTES, PROPOSALS) if os.path.exists(os.path.join(ROOT, p))]
    if extra:
        git("add", "-A", "--", *extra)
    git("commit", "-q", "-m", "mm land %s" % s["stem"])
    print("landed %s" % s["stem"])
    return 0

def cmd_tag(a):
    rel = a.release
    need(rel not in tags(), "%s is already tagged" % rel)
    exs, sls = examples()[0], slices()
    need(any(s["release"] == rel for s in sls), "no slice has Release: %s" % rel)
    holds = release_ready(rel, exs, sls, config())
    need(not holds, "%s: %s" % (rel, "; ".join(why for _, why in holds)))
    need(not dirty(), "the tree is dirty")
    r = at_head(reviews(rel), head())
    need(r, "%s: no release review at HEAD %s: the conductor runs one" % (rel, head()[:12]))
    need(r["verdict"] == "HEALTHY" or a.why, "%s: review %d is DESIGN-PASS: `tag %s --why '…'` records why its "
         "findings are accepted" % (rel, r["k"], rel))
    gate()
    drop_drafts()
    kept = [p for p in (REVIEWS, "%s/%s" % (SHOTS, rel)) if os.path.isdir(os.path.join(ROOT, p))]
    if r["verdict"] != "HEALTHY":
        kept.append(accepted(rel, r, a.why))
    if kept:
        git("add", "-A", "--", *kept)
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--", *kept], cwd=ROOT).returncode:
            git("commit", "-q", "-m", "review: %s" % rel, "--", *kept)
    git("tag", "-a", rel, "-m", "mismagent release %s — review %d %s" % (rel, r["k"], r["verdict"]))
    print("tagged %s at %s" % (rel, head()[:12]))
    return 0

def accepted(rel, r, why):
    """Writes the decision that tags rel over review r's open findings, in the human's words; -> its path."""
    os.makedirs(os.path.join(ROOT, M, "decisions"), exist_ok=True)
    path = "%s/decisions/%04d-confirm-%s.md" % (M, next_number(), rel)
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        f.write("# %s tagged over review %d (%s)\n\nThe human, %s: \"%s\"\n\n## Evidence\n- %s at %s\n"
                % (rel, r["k"], r["verdict"], time.strftime("%Y-%m-%d"), why, r["path"], r["sha"]))
    return path

def next_number():
    """The next four-digit number unused in decisions/ and stack-reviews/ (specify reserves them in both)."""
    used = [int(n[:4]) for d in (M + "/decisions", STACK_REVIEWS) for n in ls(d) if re.match(r"\d{4}", n)]
    return max(used, default=0) + 1

SUBCOMMANDS = (  # name, help, positional argument (name, help) or a --json flag
    ("status", "slices per state and release, examples vs acceptance tests, notes", "--json"),
    ("next", "exactly one next action: <action> <arg...> — <reason>", "--json"),
    ("start", "todo -> doing, write Base:, commit (clean tree, nothing in doing)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("park", "doing -> todo, drop Base:, commit (clean tree, no work since Base)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("built", "the builder is done: gate green, write Built: <round>, commit",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("review", "write the next review file from its draft (HEAD unchanged since --sha)",
     ("target", "slice stem or number, or release token")),
    ("land", "doing -> done, commit (PASS at HEAD, clean tree, gate green)",
     ("slice", "slice stem (NN-name), its number, or its path")),
    ("gate", "run check, then test and lint from CLAUDE.md ## mismagent (--base: the slice's files too)", None),
    ("shot", "render the screens of a slice's or a release's artboards (Design:) with the project's "
     "shot command, into .mismagent/shots/<target>/; prints each pair",
     ("target", "slice stem or number, or release token")),
    ("tag", "git tag -a <release> (ready, clean tree, a review at HEAD — DESIGN-PASS with --why, gate green)",
     ("release", "release token, e.g. R0")),
    ("check", "files well formed, acceptance markers, sensors, guarded files, the releases' specs", None))

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
    rv = sub.choices["review"]
    rv.add_argument("verdict", help="PASS | REWORK | DIRECT (a slice), HEALTHY | DESIGN-PASS (a release)")
    rv.add_argument("--sha", required=True, help="the HEAD you read when the review began")
    rv.add_argument("--body", help="file with the checklist and the findings "
                    "(default: .mismagent/reviews/<target>.draft.md, removed once used)")
    sub.choices["tag"].add_argument("--why", help="the human's words accepting a DESIGN-PASS review's findings, "
                                    "written as .mismagent/decisions/NNNN-confirm-<release>.md")
    for name in ("check", "gate"):
        sub.choices[name].add_argument("--base", help="also refuse the human's files changed since this ref, "
                                       "and list the other examples' acceptance files the slice touched")
    sub.choices["check"].add_argument("--release", help="also refuse what does not hold together in this "
                                      "release's spec: an example in no slice, a feature or fix slice with no "
                                      "example, no release file or open questions in it (specify, before closing)")
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
