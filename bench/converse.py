#!/usr/bin/env python3
"""converse.py — a builder session and a simulated user, in turns, until a release tag appears.

The builder is plain `claude -p` in the project (no plugin), one session resumed turn after turn.
After each builder turn, a separate simulated-user agent (no tools) reads the builder's last message
and answers as the product owner would. The phase ends when the tag appears, or on a stop rule.

  converse.py --project P --phase B --tag R0 --opening-file open.md --sim-file sim-user.md \
              --goal "R0 = …" --budget-usd 30 [--model sonnet] [--job-dir J] [--max-turns 40]

With `--until-marker TEXT` instead of `--tag`, the phase ends (outcome `marked`) when the builder's
message contains TEXT — e.g. `SPECIFIED R0` at the end of `/mismagent:specify`. `--plugin-dir` loads
a plugin into the builder's session.

Prints one JSON object: outcome (released | marked | budget | no-progress | max-turns | sim-stop |
cli-error | cost-invalid), costs, turns, questions answered, policy gaps. Stdlib only.
"""
import argparse
import json
import os
import subprocess
import sys

SIM_KINDS = ("answer", "continue", "confirm", "stop")


class Stop(Exception):
    def __init__(self, outcome, reason):
        super().__init__(reason)
        self.outcome, self.reason = outcome, reason


def git(project, *args):
    r = subprocess.run(["git", "-C", project, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def progress_mark(project):
    """What counts as progress: a new commit or a new tag."""
    return git(project, "rev-parse", "HEAD") + "|" + git(project, "tag", "-l")


def call_claude(a, args, cwd):
    env = dict(os.environ, CLAUDE_CODE_DISABLE_BACKGROUND_TASKS="1")
    r = subprocess.run([a.claude, "-p", "--output-format", "json", "--model", a.model, *args],
                       cwd=cwd, capture_output=True, text=True, env=env)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        raise Stop("cli-error", "not JSON (exit %d): %s" % (r.returncode, (r.stdout or r.stderr)[-300:]))
    cost = out.get("total_cost_usd")
    if not isinstance(cost, (int, float)) or cost < 0:
        raise Stop("cost-invalid", "total_cost_usd missing or invalid: %r" % (cost,))
    return out


def sim_prompt(a, builder_text):
    requisiti = open(os.path.join(a.project, "REQUISITI.md")).read()
    return "%s\n\n## Phase goal\n%s\n\n## REQUISITI.md (current)\n%s\n\n## The builder's last message\n%s" % (
        open(a.sim_file).read(), a.goal, requisiti, builder_text)


def parse_sim(text):
    """The simulated user answers with one JSON object; take the last {...} in the text."""
    start = text.rfind("{")
    while start >= 0:
        try:
            d = json.loads(text[start:text.rindex("}") + 1])
            if d.get("kind") in SIM_KINDS and isinstance(d.get("message", ""), str):
                return d
        except ValueError:
            pass
        start = text.rfind("{", 0, start)
    raise Stop("cli-error", "simulated user gave no valid JSON: %s" % text[-300:])


def run(a):
    log = open(os.path.join(a.job_dir, "%s-transcript.jsonl" % a.phase), "a")
    state = {"builder_usd": 0.0, "sim_usd": 0.0, "turns": 0, "questions": 0, "gaps": 0, "session_id": None}

    def spent():
        return state["builder_usd"] + state["sim_usd"]

    def record(**kw):
        log.write(json.dumps(kw, ensure_ascii=False) + "\n"); log.flush()

    message, cum, idle, outcome, reason = open(a.opening_file).read(), 0.0, 0, None, ""
    last_text = ""
    try:
        while True:
            if a.tag and git(a.project, "tag", "-l", a.tag):
                outcome, reason = "released", "tag %s exists" % a.tag; break
            if a.until_marker and state["turns"] and a.until_marker in last_text:
                outcome, reason = "marked", a.until_marker; break
            if state["turns"] >= a.max_turns:
                outcome, reason = "max-turns", "%d builder turns" % a.max_turns; break
            left = a.budget_usd - spent()
            if left <= 0.05:
                outcome, reason = "budget", "spent %.2f of %.2f" % (spent(), a.budget_usd); break
            before = progress_mark(a.project)
            args = ["--permission-mode", "bypassPermissions", "--max-budget-usd", "%.4f" % left]
            args += ["--plugin-dir", a.plugin_dir] if a.plugin_dir else []
            args += ["--resume", state["session_id"]] if state["session_id"] else []
            out = call_claude(a, args + [message], a.project)
            if out["total_cost_usd"] < cum:
                raise Stop("cost-invalid", "cumulative total_cost_usd went down")
            state["builder_usd"] += out["total_cost_usd"] - cum
            cum = out["total_cost_usd"]
            state["session_id"] = out.get("session_id") or state["session_id"]
            state["turns"] += 1
            text = last_text = out.get("result") or ""
            record(role="builder", turn=state["turns"], cost_usd=round(spent(), 4), subtype=out.get("subtype"), text=text)
            if (a.tag and git(a.project, "tag", "-l", a.tag)) or (a.until_marker and a.until_marker in text):
                continue
            if out.get("subtype") == "error_max_budget_usd":
                outcome, reason = "budget", "builder hit the cap"; break
            idle = 0 if progress_mark(a.project) != before else idle + 1
            if idle >= a.no_progress and not a.until_marker:  # an interview commits only at its close
                outcome, reason = "no-progress", "%d builder turns without a commit or tag" % idle; break
            if a.budget_usd - spent() <= 0.05:
                continue   # the loop head stops on the budget; no user turn to pay for
            sim = call_claude(a, ["--tools", "", "--max-budget-usd", "1", sim_prompt(a, text)], a.job_dir)
            state["sim_usd"] += sim["total_cost_usd"]
            reply = parse_sim(sim.get("result") or "")
            state["questions"] += reply["kind"] == "answer"
            state["gaps"] += bool(reply.get("gap"))
            record(role="user", kind=reply["kind"], gap=bool(reply.get("gap")), text=reply.get("message", ""))
            if reply["kind"] == "stop":
                outcome, reason = "sim-stop", reply.get("message", ""); break
            message = reply.get("message") or "Prosegui."
    except Stop as s:
        outcome, reason = s.outcome, s.reason
    result = {"phase": a.phase, "outcome": outcome, "reason": reason, "tag": a.tag,
              "builder_usd": round(state["builder_usd"], 4), "sim_usd": round(state["sim_usd"], 4),
              "total_cost_usd": round(spent(), 4), "turns": state["turns"],
              "questions": state["questions"], "policy_gaps": state["gaps"], "session_id": state["session_id"]}
    record(role="result", **result)
    log.close()
    return result


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--tag", help="the phase ends when this git tag exists")
    ap.add_argument("--until-marker", help="the phase ends when the builder's message contains this text")
    ap.add_argument("--plugin-dir", help="load this plugin into the builder's session")
    ap.add_argument("--opening-file", required=True, help="the user's first message to the builder")
    ap.add_argument("--sim-file", required=True, help="the simulated user's instructions")
    ap.add_argument("--goal", required=True, help="what the simulated user waits for in this phase")
    ap.add_argument("--budget-usd", type=float, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--job-dir", default=".")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--no-progress", type=int, default=3)
    ap.add_argument("--claude", default="claude")
    a = ap.parse_args(argv)
    if not (a.tag or a.until_marker):
        ap.error("--tag or --until-marker is required")
    a.plugin_dir = a.plugin_dir and os.path.abspath(a.plugin_dir)
    a.project, a.job_dir = os.path.abspath(a.project), os.path.abspath(a.job_dir)
    os.makedirs(a.job_dir, exist_ok=True)
    return a


def main(argv=None):
    r = run(parse(argv))
    print(json.dumps(r))
    return 0 if r["outcome"] in ("released", "marked") else 1


if __name__ == "__main__":
    sys.exit(main())
