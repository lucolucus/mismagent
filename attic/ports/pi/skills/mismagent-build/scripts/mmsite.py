#!/usr/bin/env python3
"""mm site — a read-only picture of the project, one self-contained HTML page (stdlib only).

Reads what mm reads (slices, examples, reviews, acceptance markers, tags) plus the brief, the event
storm, the decisions, the conventions skill and git's log, and writes them as JSON into `mmsite.html`,
which draws four views: progress (one lane per release), requirements (requirement -> examples ->
slices -> tests), conventions, decisions. Never moves state, never writes inside the repository
unless told to with --out.

Requirements are the ids the examples' `req` column cites, read tolerantly: a bare number or
`event N` is the event storm's timeline row N; `A1`, `S12`, `H1`... are codes defined in the brief or
the event storm (the line that starts with the code, else the first line naming it) — a family
(`S`, `I`...) is listed whole once the examples cite one of it, hotspots `H<n>` always; `decision NNNN`
is decisions/NNNN-*.md. Ranges (`1-3`, `F0–F2`) are expanded.

Usage (from inside the project): python3 mmsite.py --serve [--open]   live, see mmsite_live.py
                                 python3 mmsite.py [--out FILE] [--open]   one snapshot (default: a temp file)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import mm
import mmsite_live

HERE = os.path.dirname(os.path.abspath(__file__))
EVENT_STORM, ARCHITECTURE = mm.M + "/event-storm.md", "ARCHITECTURE.md"
RELEASES, DECISIONS, PROGRESS = mm.M + "/releases", mm.M + "/decisions", mm.M + "/progress.md"
CODE = re.compile(r"\b([A-Z]{1,2})(\d+)\b")
RANGE = re.compile(r"\b([A-Z]{0,2})(\d+)\s*[-–—]\s*\1?(\d+)\b")
RELEASE_TITLE = re.compile(r"\*\*(R\d+)\s*[—–-]\s*([^*]+)\*\*")
FIELD = re.compile(r"^[-*\s]*(kind|release|examples|base|after|built)\s*:", re.I)

def sections(text):
    """-> [(heading, body)] of the `## ` sections; the text before the first is ('', preamble)."""
    out, cur, body = [], "", []
    for line in text.splitlines():
        h = re.match(r"^##\s+(.*)$", line)
        if h:
            out.append((cur, "\n".join(body).strip()))
            cur, body = h.group(1).strip(), []
        else:
            body.append(line)
    out.append((cur, "\n".join(body).strip()))
    return [s for s in out if s[0] or s[1]]

def table_rows(text):
    """-> the cells of each data row of the markdown tables in text (header and rule skipped)."""
    rows, header = [], True
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header = True
            continue
        if re.fullmatch(r"[|:\-\s]+", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header:
            header = False
            continue
        rows.append(cells)
    return rows

def commits():
    """-> [{sha, date, subject}] newest first."""
    out = mm.git("log", "--format=%h%x09%ad%x09%s", "--date=short", check=False)
    return [dict(zip(("sha", "date", "subject"), l.split("\t", 2))) for l in out.splitlines() if l.count("\t") >= 2]

def review_body(r):
    text = mm.read(r["path"])
    scores = re.search(r"^[\s*_>-]*SCORES[\s*_]*:(.*)$", text, re.M | re.I)
    body = "\n".join(l for l in text.splitlines()
                     if not re.match(r"^[\s*_>-]*(VERDICT|SHA|SCORES)[\s*_]*:", l, re.I)).strip()
    return dict(k=r["k"], verdict=r["verdict"], sha=r["sha"][:7], why=r["why"], body=body,
                scores=dict(re.findall(r"([\w-]+)\s*=\s*([0-9-])", scores.group(1))) if scores else {})

def old_progress():
    """-> {slice stem: [notes]} from the single progress.md of older projects (`## <stem> — date`)."""
    out = {}
    for head, body in sections(mm.read(PROGRESS)):
        m = re.match(r"^([\w-]+)(.*)$", head)
        if m and head:
            out.setdefault(m.group(1), []).append("### %s\n%s" % (head, body))
    return out

def slice_data(s, sls, log, notes, par):
    text = mm.read(s["path"])
    secs = sections(text)
    pre = "\n".join(l for l in (secs[0][1] if secs and not secs[0][0] else "").splitlines()
                    if not FIELD.match(l)).strip()
    own = [b for h, b in secs if h.lower() == "progress"]
    asked = [(h, b) for h, b in secs if h.lower() in ("question", "answer")]
    mine = [c for c in log if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(s["stem"]), c["subject"])]
    started = [c["date"] for c in mine if c["subject"].startswith("mm start")]
    landed = [c["date"] for c in mine if c["subject"].startswith("mm land")]
    return dict(stem=s["stem"], num=s["num"], title=re.sub(r"^\d+-", "", s["stem"]).replace("-", " "),
                kind=s["kind"], release=s["release"], state=s["state"], examples=s["examples"],
                after=s["after"], waits=mm.waits_for(s, sls), blocked=s["blocked"], base=s["base"][:7],
                built=s["built"], text=pre, progress="\n\n".join(own + notes.get(s["stem"], [])),
                qa=[{"h": h, "b": b} for h, b in asked], reviews=[review_body(r) for r in mm.reviews(s["stem"])],
                commits=mine, started=started[-1] if started else "", landed=landed[0] if landed else "",
                par=par.get(s["stem"]))

def worktrees():
    """-> {branch: path} of the project's other worktrees."""
    out, cur = {}, {}
    for line in mm.git("worktree", "list", "--porcelain", check=False).splitlines() + [""]:
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):]}
        elif line.startswith("branch refs/heads/"):
            cur["branch"] = line[len("branch refs/heads/"):]
        elif not line and cur.get("branch") and os.path.realpath(cur["path"]) != os.path.realpath(mm.ROOT):
            out[cur["branch"]], cur = cur["path"], {}
    return out

def parallel(sls):
    """-> {slice stem: work on it outside this checkout}: a worktree, or a branch not merged yet,
    whose last name segment is the slice (`par/14-stampa`, or its number). A landed slice's branch
    without a worktree is left over, not work."""
    base = mm.git("rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or "HEAD"
    by_stem, by_num = {s["stem"]: s for s in sls}, {s["num"]: s for s in sls}
    trees = worktrees()
    unmerged = mm.git("branch", "--no-merged", base, "--format=%(refname:short)", check=False).split()
    out = {}
    for branch in sorted(set(trees) | set(unmerged)):
        seg = branch.rsplit("/", 1)[-1]
        num = re.match(r"(\d+)-", seg)
        s = by_stem.get(seg) or (by_num.get(int(num.group(1))) if num else None)
        path = trees.get(branch, "")
        if not s or branch == base or (not path and s["state"] == "done"):
            continue
        counts = mm.git("rev-list", "--left-right", "--count", "%s...%s" % (base, branch), check=False).split()
        behind, ahead = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (0, 0)
        log = [dict(zip(("sha", "date", "subject"), l.split("\t", 2))) for l in
               mm.git("log", "--format=%h%x09%ad%x09%s", "--date=short", "%s..%s" % (base, branch),
                      check=False).splitlines() if l.count("\t") >= 2]
        dirty, progress = 0, ""
        if path:
            st = subprocess.run(["git", "-C", path, "status", "--porcelain"], capture_output=True, text=True)
            dirty = sum(1 for l in st.stdout.splitlines() if l.strip())
            for state in mm.STATES:
                f = os.path.join(path, mm.M, "slices", state, s["stem"] + ".md")
                if os.path.isfile(f):
                    with open(f, encoding="utf-8") as fh:
                        progress = "\n\n".join(b for h, b in sections(fh.read()) if h.lower() == "progress")
                    break
        out[s["stem"]] = dict(branch=branch, path=path, base=base, ahead=ahead, behind=behind, dirty=dirty,
                              commits=log[:20], progress=progress)
    return out

def expand(cell):
    """The requirement ids a `req` cell cites: `event:N`, `code:S12`, `decision:0005`."""
    ids, rest = [], cell
    for m in re.finditer(r"decisions?\s+(\d{3,4})", cell, re.I):
        ids.append("decision:%04d" % int(m.group(1)))
    rest = re.sub(r"decisions?\s+\d{3,4}|EX-\d+", " ", rest, flags=re.I)
    for m in RANGE.finditer(rest):
        pre, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        ids += [("code:%s%d" % (pre, n)) if pre else "event:%d" % n for n in range(lo, hi + 1)]
    rest = RANGE.sub(" ", rest)
    for tok in re.findall(r"\b[A-Z]{0,2}\d+\b", rest):
        ids.append("event:%s" % tok if tok.isdigit() else "code:%s" % tok)
    return [i for i in dict.fromkeys(ids) if not re.fullmatch(r"code:R\d+", i)]  # a release is no requirement

def code_text(code, docs):
    """What a code like `S12` means: the line that starts with it, else the first line naming it."""
    lines = [(name, l.strip()) for name, text in docs for l in text.splitlines()]
    pat = re.compile(r"(?<![\w-])%s(?![\w])" % re.escape(code))
    start = [x for x in lines if re.match(r"^[-*>\s]*(\*\*)?%s\b" % re.escape(code), x[1])]
    named = [x for x in lines if pat.search(x[1])]
    hit = (start or named or [("", "")])[0]
    return hit[0], re.sub(r"^[-*>\s]+", "", hit[1])

def requirements(exs_full):
    storm, brief = mm.read(EVENT_STORM), mm.read(mm.BRIEF)
    reqs = {}
    timeline = dict(sections(storm)).get("Timeline", "")
    for cells in table_rows(timeline):
        if cells and cells[0].isdigit() and len(cells) > 1:
            reqs["event:%s" % cells[0]] = dict(id="event:%s" % cells[0], group="event storm",
                                               label="#%s %s" % (cells[0], cells[1]),
                                               text=" · ".join(c for c in cells[2:] if c and c not in "–-"),
                                               source=EVENT_STORM)
    for name in mm.ls(DECISIONS):
        m = re.match(r"(\d+)-(.*)\.md$", name)
        if m:
            first = next((l.lstrip("# ").strip() for l in mm.read("%s/%s" % (DECISIONS, name)).splitlines()
                          if l.strip()), "")
            rid = "decision:%04d" % int(m.group(1))
            reqs[rid] = dict(id=rid, group="decision", label="%s %s" % (m.group(1), m.group(2).replace("-", " ")),
                             text=first, source="%s/%s" % (DECISIONS, name))
    docs = [(EVENT_STORM, storm), (mm.BRIEF, brief)]  # a hotspot's own line before the brief's mention
    # a code family counts when the examples cite one of it (S1..S13 of a brief), or it is a hotspot
    cited = {i for e in exs_full for i in e["reqs"] if i.startswith("code:")}
    families = {re.sub(r"\d", "", c) for c in cited} | {"code:H"}
    codes = cited | {"code:%s%s" % m for _, t in docs for m in CODE.findall(t) if "code:" + m[0] in families}
    for rid in sorted(codes, key=lambda c: (re.sub(r"\d", "", c), int(re.sub(r"\D", "", c) or 0))):
        code = rid.split(":", 1)[1]
        if re.fullmatch(r"R\d+|EX\d*", code):
            continue
        src, text = code_text(code, docs)
        reqs[rid] = dict(id=rid, group="hotspot" if code.startswith("H") and src == EVENT_STORM else "brief",
                         label=code, text=text, source=src)
    for e in exs_full:
        for i in e["reqs"]:
            reqs.setdefault(i, dict(id=i, group="unknown", label=i.split(":", 1)[1], text="not found", source=""))
    return list(reqs.values())

def examples_full(sls, marks):
    rows = []
    for rel in mm.example_files():
        cap = os.path.basename(rel)[:-3]
        for c in table_rows(mm.read(rel)):
            if len(c) == 7 and mm.EX_ID.match(c[0]):
                by = re.search(r"superseded\s+by\s+(EX-\d+)", c[3], re.I)
                rows.append(dict(id=c[0], given=c[1], when=c[2], then=c[3], rule=c[4], req=c[5], release=c[6],
                                 capability=cap, superseded=by.group(1) if by else "", reqs=expand(c[5]),
                                 tests=sorted(marks.get(c[0], [])),
                                 slices=[s["stem"] for s in sls if c[0] in s["examples"]]))
    return rows

def release_detail(rid):
    own = mm.read("%s/%s.md" % (RELEASES, rid))
    if own:  # its own file, titled `# R1 — <what it delivers>`
        head = re.match(r"#\s*%s\s*[—–:-]\s*(.+)" % re.escape(rid), own.lstrip())
        return (head.group(1).strip() if head else ""), own
    brief = mm.read(mm.BRIEF).splitlines()
    for i, line in enumerate(brief):
        m = RELEASE_TITLE.search(line)
        if m and m.group(1) == rid:
            block = [line]
            for l in brief[i + 1:]:
                if l.startswith("#") or RELEASE_TITLE.search(l):
                    break
                block.append(l)
            return m.group(2).strip().rstrip(":"), "\n".join(block).strip()
    return "", ""

def releases(exs, sls, tagged):
    named = [m.group(1) for m in RELEASE_TITLE.finditer(mm.read(mm.BRIEF))]
    named += [n[:-3] for n in mm.ls(RELEASES) if n.endswith(".md")]
    order = list(dict.fromkeys(mm.release_order(exs, sls) + named))
    order.sort(key=lambda r: int(re.sub(r"\D", "", r) or 0))
    out = []
    for rid in order:
        title, detail = release_detail(rid)
        out.append(dict(id=rid, title=title, detail=detail, tagged=rid in tagged,
                        reviews=[review_body(r) for r in mm.reviews(rid)]))
    return out

def conventions():
    files = sorted(r for r in mm.walk(mm.SKILL) if r.endswith(".md"))
    files.sort(key=lambda r: (not r.endswith("SKILL.md"), r))
    return [dict(path=r, name=os.path.basename(r)[:-3], text=mm.read(r)) for r in files]

def items(rel):
    return [l.lstrip()[2:].strip() for l in mm.read(rel).splitlines() if l.lstrip().startswith("- ")]

def collect():
    sls = sorted(mm.slices(), key=lambda s: s["num"])
    exs, ex_errors = mm.examples()
    marks, tagged, log = mm.markers(), mm.tags(), commits()
    try:
        nxt = mm.decide()
    except mm.Refused as e:
        nxt = dict(action="?", reason=str(e))
    notes = old_progress()
    exs_full = examples_full(sls, marks)
    par = parallel(sls)
    return dict(
        project=os.path.basename(mm.ROOT), generated=time.strftime("%Y-%m-%d %H:%M:%S"),
        head=mm.git("rev-parse", "--short", "HEAD", check=False).strip(), next=nxt,
        releases=releases(exs, sls, tagged), slices=[slice_data(s, sls, log, notes, par) for s in sls],
        examples=exs_full, requirements=requirements(exs_full), example_errors=ex_errors,
        conventions=conventions(), proposals=items(mm.PROPOSALS), notes=items(mm.NOTES),
        decisions=[dict(path="%s/%s" % (DECISIONS, n), name=n[:-3], text=mm.read("%s/%s" % (DECISIONS, n)))
                   for n in mm.ls(DECISIONS) if n.endswith(".md")],
        docs=[dict(path=p, text=mm.read(p)) for p in (mm.BRIEF, EVENT_STORM, ARCHITECTURE) if mm.read(p)],
        log=log[:200])

def render(data):
    with open(os.path.join(HERE, "mmsite.html"), encoding="utf-8") as f:
        page = f.read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return page.replace("/*DATA*/null", blob).replace("{{project}}", data["project"])

def main(argv=None):
    p = argparse.ArgumentParser(description="a read-only HTML picture of the project")
    p.add_argument("--serve", action="store_true", help="keep it live: start (or reuse) the project's "
                   "local server and print its URL; the page follows the project by itself")
    p.add_argument("--stop", action="store_true", help="stop the project's server")
    p.add_argument("--serve-here", action="store_true", help=argparse.SUPPRESS)  # the server itself
    p.add_argument("--out", help="write a snapshot to this file (default: a temp file)")
    p.add_argument("--open", action="store_true", help="open it in the browser")
    a = p.parse_args(argv)
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode:
        print("mm: not inside a git repository", file=sys.stderr)
        return 1
    mm.ROOT = top.stdout.strip()
    if a.serve_here:
        return mmsite_live.serve(collect, render)
    if a.stop:
        print("stopped" if mmsite_live.stop() else "no server running")
        return 0
    try:
        out = mmsite_live.start(os.path.abspath(__file__)) if a.serve else snapshot(a.out)
    except mm.Refused as e:
        print("mm: %s" % e, file=sys.stderr)
        return 1
    print(out)
    if a.open:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", out], check=False)
    return 0

def snapshot(out):
    out = out or os.path.join(tempfile.gettempdir(), "mismagent-%s.html" % os.path.basename(mm.ROOT))
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(collect()))
    return out

if __name__ == "__main__":
    sys.exit(main())
