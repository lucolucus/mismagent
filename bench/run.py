#!/usr/bin/env python3
"""Headless build runner: re-invokes the worker-composer until the TOOL says the feature is done or
idle, or a dollar cap is reached. Runner-side, never part of the core. Stdlib only.

Serial firings of
    claude -p --plugin-dir <plugin> --output-format json --max-budget-usd <min(per_firing, remaining)>
           [--model M] [--resume <session_id>] "/mismagent:worker-composer <feature>[\\n\\n<prompt-file>]"
with CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1. After each firing it reads `mismagent.py status`
(never the report text). No timeout, no polling, no sleep, no automatic recovery: any doubt stops.

    python3 bench/run.py --project P --feature F --plugin-dir plugins/mismagent --total-usd 20 --per-firing-usd 5
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys

STOP_OUTCOMES = ("done", "idle", "anomaly")
MIN_CLI = (2, 1, 277)  # from here `total_cost_usd` is cumulative on --resume: the deltas are right
BOOKKEEPING = re.compile(r"(\.log$|report|ledger)", re.I)  # worktree files that are not progress


class Stop(Exception):
    def __init__(self, outcome, reason):
        super().__init__(reason)
        self.outcome, self.reason = outcome, reason


def feature_dir(project, feature):
    """<project>/<output_dir>/features/<feature> (or <project>/features/<feature>): exactly one."""
    bases = [project] + [os.path.join(project, d) for d in sorted(os.listdir(project))]  # `*` skips `.mismagent`
    hits = [os.path.join(b, "features", feature) for b in bases
            if os.path.isfile(os.path.join(b, "features", feature, "building-blocks.yaml"))]
    if len(hits) != 1:
        raise SystemExit("run.py: %d feature dirs named %r under %s (pass --feature-dir)" % (len(hits), feature, project))
    return hits[0]


def status(tool, fdir, integration):
    """The tool's status JSON (exit 0 = no anomaly, 1 = anomalies; anything else is an error)."""
    p = subprocess.run([sys.executable, tool, "status", fdir, "--integration", integration],
                       capture_output=True, text=True)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    if p.returncode not in (0, 1) or not isinstance(out, dict) or out.get("outcome") not in STOP_OUTCOMES + ("work",):
        raise Stop("status-error", "mismagent.py status exit %d: %s" % (p.returncode, (p.stdout + p.stderr).strip()[-400:]))
    return out


def _sha_field(path):
    try:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return "unreadable"
    return rec.get("sha") if isinstance(rec, dict) else "unreadable"


def _digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode() + b"\0")
        with open(p, "rb") as f:
            h.update(f.read() + b"\0")
    return h.hexdigest()


def cli_version(claude_bin):
    """Refuse a CLI older than MIN_CLI: before it each invocation reports its own cost, not the total."""
    try:
        p = subprocess.run([claude_bin, "--version"], capture_output=True, text=True)
    except OSError as e:
        raise Stop("cli-error", "%s --version: %s" % (claude_bin, e))
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", p.stdout)
    v = tuple(int(x) for x in m.groups()) if m and p.returncode == 0 else None
    if not v or v < MIN_CLI:
        raise Stop("cli-version", "Claude Code %s < %s: cost deltas need a cumulative total_cost_usd on --resume; "
                   "upgrade the CLI" % (".".join(map(str, v)) if v else repr((p.stdout + p.stderr).strip()[-80:]),
                                        ".".join(map(str, MIN_CLI))))
    return v


def _git(cwd, *args):
    p = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else "git error: " + p.stderr.strip()


def worktree_changes(fdir):
    """{branch: hash} of the uncommitted content (`git status --porcelain` + each changed file's
    content) in the block/spike worktrees; bookkeeping files (logs, reports, ledgers) ignored."""
    out, wt = {}, None
    for line in _git(fdir, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            wt = line[9:]
        elif line.startswith(("branch refs/heads/block/", "branch refs/heads/spike/")) and os.path.isdir(wt):
            h = hashlib.sha256()
            for entry in sorted(_git(wt, "status", "--porcelain", "--untracked-files=all").splitlines()):
                path = entry[3:].split(" -> ")[-1].strip('"')
                if BOOKKEEPING.search(os.path.basename(path)):
                    continue
                h.update(entry.encode() + b"\0")
                f = os.path.join(wt, path)
                if os.path.isfile(f):
                    with open(f, "rb") as fh:
                        h.update(fh.read() + b"\0")
            out[line[18:]] = h.hexdigest()
    return out


def snapshot(fdir):
    """The structural state a firing can change. Ignored: timestamps, reports, decisions.md, the
    integration line's tip (bookkeeping commits). Branch tips are compared by TREE, so a commit that
    changes no content is no progress; spike evidence and the worktrees' uncommitted content count."""
    rel = lambda ps: sorted(os.path.relpath(p, fdir) for p in ps)
    g = lambda pat: glob.glob(os.path.join(fdir, pat))
    snap = {
        "states": rel(g("blocks/*/*/*.md") + g("tasks/*/*/*.md")),
        "specs": _digest(g("building-blocks.yaml") + g("blocks/*/*/*.md")),
        "integrated": {os.path.basename(p): _sha_field(p) for p in g("integrated/*.json")},
        "review_proofs": {os.path.basename(p): _sha_field(p) for p in g("review-proof/*.json")},
        "rework": _digest(g("rework/*.md")),
        "open_questions": rel(g("open-questions/*.md")),
        "pre_release": _digest(g("pre-release.md")),
        "spikes": {os.path.relpath(p, fdir): _digest([p]) for p in g("spikes/*.md")},
        "worktrees": worktree_changes(fdir),
    }
    p = subprocess.run(["git", "-C", fdir, "for-each-ref", "--format=%(refname) %(tree)", "refs/heads/block/",
                        "refs/heads/spike/"], capture_output=True, text=True)
    snap["branches"] = sorted(p.stdout.splitlines()) if p.returncode == 0 else ["git error: " + p.stderr.strip()]
    return snap


def firing_cmd(a, cap, session, prompt):
    cmd = [a.claude_bin, "-p", "--plugin-dir", a.plugin_dir, "--output-format", "json", "--max-budget-usd", "%.4f" % cap]
    cmd += ["--model", a.model] if a.model else []
    cmd += ["--resume", session] if session else []
    return cmd + [prompt]


def parse_result(p):
    """The CLI's JSON result, or a diagnostic Stop. A budget-exhausted firing is a valid result."""
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    if not isinstance(out, dict):
        raise Stop("cli-error", "claude exit %d, no JSON result: %s" % (p.returncode, (p.stdout + p.stderr).strip()[-400:]))
    cost = out.get("total_cost_usd")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        raise Stop("cost-invalid", "total_cost_usd missing or invalid: %r" % (cost,))
    if not out.get("session_id"):
        raise Stop("cli-error", "no session_id in the result")
    return out


def budget_exhausted(out):
    return "budget" in str(out.get("subtype", "")).lower()


def why_stop(st):
    why = st.get("anomalies") if st["outcome"] == "anomaly" else st.get("waiting")
    return json.dumps(why, ensure_ascii=False)[:400] if why else st["outcome"]


def run(a):
    tool = os.path.join(a.plugin_dir, "tools", "mismagent.py")
    fdir = a.feature_dir or feature_dir(a.project, a.feature)
    integration = a.integration or "integration/%s" % a.feature
    prompt = "/mismagent:worker-composer %s" % a.feature
    if a.prompt_file:
        with open(a.prompt_file, encoding="utf-8") as f:
            prompt += "\n\n" + f.read().strip()
    env = dict(os.environ, CLAUDE_CODE_DISABLE_BACKGROUND_TASKS="1")
    firings, spent, cum, session, still = [], 0.0, 0.0, None, 0
    summary = lambda outcome, reason: {"outcome": outcome, "reason": reason, "firings": len(firings),
                                       "total_cost_usd": round(spent, 6), "session_id": session, "log": firings}
    try:
        cli_version(a.claude_bin)
        st = status(tool, fdir, integration)
        if st["outcome"] in STOP_OUTCOMES:
            return summary(st["outcome"], "before any firing: " + why_stop(st))
        before = snapshot(fdir)
        while True:
            remaining = a.total_usd - spent
            if remaining <= 0:
                raise Stop("budget", "total budget $%.2f spent" % a.total_usd)
            cap = min(a.per_firing_usd, remaining)
            p = subprocess.run(firing_cmd(a, cap, session, prompt), cwd=a.project, env=env, capture_output=True, text=True)
            out = parse_result(p)
            if out["total_cost_usd"] < cum:
                raise Stop("cost-invalid", "cumulative total_cost_usd went down: %s < %s" % (out["total_cost_usd"], cum))
            delta, cum, session = out["total_cost_usd"] - cum, out["total_cost_usd"], out["session_id"]
            spent += delta
            rec = {"n": len(firings) + 1, "cap_usd": round(cap, 6), "cost_usd": round(delta, 6),
                   "subtype": out.get("subtype"), "is_error": bool(out.get("is_error"))}
            firings.append(rec)
            if (p.returncode != 0 or out.get("is_error")) and not budget_exhausted(out):
                raise Stop("cli-error", "claude exit %d, subtype %r: %s" % (
                    p.returncode, out.get("subtype"), str(out.get("result") or p.stderr).strip()[-400:]))
            st = status(tool, fdir, integration)
            rec["status"] = st["outcome"]
            if st["outcome"] in STOP_OUTCOMES:
                return summary(st["outcome"], why_stop(st))
            now = snapshot(fdir)
            rec["progress"] = now != before
            still, before = (0 if rec["progress"] else still + 1), now
            if still >= 2:
                raise Stop("no-progress", "two consecutive firings changed no structural state")
    except Stop as s:
        return summary(s.outcome, s.reason)


def parse(argv=None):
    ap = argparse.ArgumentParser(description="re-invoke the worker-composer headless until done/idle or a $ cap")
    ap.add_argument("--project", required=True, help="the project repo (the claude working directory)")
    ap.add_argument("--feature", required=True)
    ap.add_argument("--plugin-dir", required=True)
    ap.add_argument("--total-usd", type=float, required=True)
    ap.add_argument("--per-firing-usd", type=float, required=True)
    ap.add_argument("--model")
    ap.add_argument("--prompt-file", help="extra instructions appended to the command (e.g. simulated-user rules)")
    ap.add_argument("--integration", help="the integration branch (default integration/<feature>)")
    ap.add_argument("--feature-dir", help="F, when it cannot be found under --project")
    ap.add_argument("--claude-bin", default="claude", help=argparse.SUPPRESS)  # tests: a simulated CLI
    a = ap.parse_args(argv)
    if not (a.total_usd > 0 and a.per_firing_usd > 0):
        ap.error("--total-usd and --per-firing-usd must be > 0")
    a.project, a.plugin_dir = os.path.abspath(a.project), os.path.abspath(a.plugin_dir)
    return a


def main(argv=None):
    out = run(parse(argv))
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["outcome"] in ("done", "idle") else 1


if __name__ == "__main__":
    sys.exit(main())
