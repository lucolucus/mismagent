#!/usr/bin/env python3
"""build_loop.py — fires `/mismagent:build` (0.5) headless, one action per firing, until a release tag.

Each firing is a fresh `claude -p --plugin-dir <plugin>` session in the project. The conductor's
report may end with `NEEDS-HUMAN: confirm <RN>` — the simulated user's policy is the consent, so
the next firing carries `--confirm <RN>` — or `NEEDS-HUMAN: <slice file>` — a separate
simulated-user agent (no tools) reads the slice file and answers; the answer is appended under
`## Answer` and committed, as the human would.

  build_loop.py --project P --plugin-dir D --release R0 --sim-file sim-user.md --budget-usd 30 \
                [--model sonnet] [--job-dir J] [--max-firings 80] [--no-progress 4]

Prints one JSON object: outcome (released | budget | no-progress | idle | max-firings | cli-error |
cost-invalid), costs, firings, human answers. Stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import converse  # same directory: git(), progress_mark(), call_claude(), parse_sim(), Stop

NEEDS = re.compile(r"NEEDS-HUMAN:[\s`'\"*]*(confirm[\s`'\"*]+([A-Za-z]+\d+)|([\w./-]+\.md))")


def answer_slice(a, rel, state):
    path = os.path.join(a.project, rel)
    text = open(path).read()
    prompt = "%s\n\n## Phase goal\nRelease %s.\n\n## REQUISITI.md (current)\n%s\n\n## The builder's last message\n" \
             "A slice is blocked on a question. Its file:\n\n%s" % (
                 open(a.sim_file).read(), a.release, open(os.path.join(a.project, "REQUISITI.md")).read(), text)
    out = converse.call_claude(a, ["--tools", "", "--max-budget-usd", "1", prompt], a.job_dir)
    state["sim_usd"] += out["total_cost_usd"]
    reply = converse.parse_sim(out.get("result") or "")
    if reply["kind"] == "stop":
        raise converse.Stop("sim-stop", reply.get("message", ""))
    with open(path, "a") as f:
        f.write("\n## Answer\n%s\n" % reply.get("message", "").strip())
    subprocess.run(["git", "-C", a.project, "add", rel], check=True)
    subprocess.run(["git", "-C", a.project, "commit", "-q", "-m", "answer: %s" % os.path.basename(rel)], check=True)
    state["answers"] += 1
    return reply


def run(a):
    log = open(os.path.join(a.job_dir, "build-%s.jsonl" % a.release), "a")
    state = {"builder_usd": 0.0, "sim_usd": 0.0, "firings": 0, "answers": 0, "confirmed": False}
    spent = lambda: state["builder_usd"] + state["sim_usd"]  # noqa: E731
    idle, outcome, reason, confirm = 0, None, "", False
    try:
        while True:
            if converse.git(a.project, "tag", "-l", a.release):
                outcome, reason = "released", "tag %s exists" % a.release; break
            if state["firings"] >= a.max_firings:
                outcome, reason = "max-firings", str(a.max_firings); break
            left = a.budget_usd - spent()
            if left <= 0.05:
                outcome, reason = "budget", "spent %.2f of %.2f" % (spent(), a.budget_usd); break
            before = converse.progress_mark(a.project)
            cmd = "/mismagent:build" + (" --confirm %s" % a.release if confirm else "")
            out = converse.call_claude(a, ["--plugin-dir", a.plugin_dir, "--permission-mode", "bypassPermissions",
                                           "--max-budget-usd", "%.4f" % left, cmd], a.project)
            state["builder_usd"] += out["total_cost_usd"]
            state["firings"] += 1
            text = out.get("result") or ""
            log.write(json.dumps({"firing": state["firings"], "cmd": cmd, "cost_usd": round(spent(), 4),
                                  "subtype": out.get("subtype"), "text": text}, ensure_ascii=False) + "\n"); log.flush()
            m = NEEDS.search(text)
            if m and m.group(2):
                confirm = m.group(2) == a.release   # the policy consents to the phase's release
                if not confirm:
                    outcome, reason = "idle", "asked to confirm %s, not %s" % (m.group(2), a.release); break
                continue
            if m and m.group(3):
                answer_slice(a, m.group(3), state)
                idle = 0
                continue
            if re.search(r"^ACTION:\s*idle", text, re.M):
                outcome, reason = "idle", text.strip().splitlines()[-1][:200]; break
            idle = 0 if converse.progress_mark(a.project) != before else idle + 1
            if idle >= a.no_progress:
                outcome, reason = "no-progress", "%d firings without a commit or tag" % idle; break
    except converse.Stop as s:
        outcome, reason = s.outcome, s.reason
    result = {"release": a.release, "outcome": outcome, "reason": reason, "builder_usd": round(state["builder_usd"], 4),
              "sim_usd": round(state["sim_usd"], 4), "total_cost_usd": round(spent(), 4),
              "firings": state["firings"], "answers": state["answers"]}
    log.write(json.dumps(dict(result, role="result")) + "\n"); log.close()
    return result


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--plugin-dir", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--sim-file", required=True)
    ap.add_argument("--budget-usd", type=float, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--job-dir", default=".")
    ap.add_argument("--max-firings", type=int, default=80)
    ap.add_argument("--no-progress", type=int, default=4)
    ap.add_argument("--claude", default="claude")
    a = ap.parse_args(argv)
    a.project, a.job_dir, a.plugin_dir = (os.path.abspath(p) for p in (a.project, a.job_dir, a.plugin_dir))
    os.makedirs(a.job_dir, exist_ok=True)
    return a


def main(argv=None):
    r = run(parse(argv))
    print(json.dumps(r))
    return 0 if r["outcome"] == "released" else 1


if __name__ == "__main__":
    sys.exit(main())
