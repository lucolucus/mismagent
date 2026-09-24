"""Tests for bench/run.py — a SIMULATED claude CLI and a simulated status tool; the real CLI is never called.
Run: python3 -m unittest discover -s bench/tests -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import run  # noqa: E402

# The fake `claude`: pops the next scripted firing, logs argv + env, applies its effects, prints its output.
SIM_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
root = os.environ["SIM_ROOT"]
if sys.argv[1:] == ["--version"]:   # not a firing: not logged
    print(os.environ.get("SIM_VERSION", "2.1.277 (Claude Code)")); sys.exit(0)
steps = json.load(open(os.path.join(root, "scenario.json")))
n = len(open(os.path.join(root, "calls.log")).read().splitlines()) if os.path.exists(os.path.join(root, "calls.log")) else 0
with open(os.path.join(root, "calls.log"), "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "bg": os.environ.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS")}) + "\n")
if n >= len(steps):
    print("scenario exhausted"); sys.exit(3)
s = steps[n]
feat = os.environ["SIM_FEAT"]
for rel, text in s.get("write", {}).items():
    p = os.path.join(feat, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(text)
if "status" in s:
    json.dump(s["status"], open(os.path.join(feat, "sim-status.json"), "w"))
for br, content in s.get("commit", {}).items():   # a commit on a block branch (content None = empty commit)
    repo = os.environ["SIM_REPO"]
    wt = os.path.join(root, "wt")
    subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "-B", br, wt, br if subprocess.run(
        ["git", "-C", repo, "rev-parse", "--verify", "-q", br], capture_output=True).returncode == 0 else "main"], check=True)
    if content is None:
        subprocess.run(["git", "-C", wt, "commit", "-q", "--allow-empty", "-m", "bookkeeping"], check=True)
    else:
        open(os.path.join(wt, "code.txt"), "w").write(content)
        subprocess.run(["git", "-C", wt, "add", "."], check=True)
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", "code"], check=True)
    subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], check=True)
out = s["out"]
print(out if isinstance(out, str) else json.dumps(out))
sys.exit(s.get("code", 0))
'''
# The fake tool: `status` prints the scripted status.
SIM_TOOL = r'''#!/usr/bin/env python3
import json, os, sys
st = json.load(open(os.path.join(sys.argv[2], "sim-status.json")))
print(json.dumps(st)); sys.exit(1 if st.get("anomalies") else 0)
'''


def res(total, sid="s-1", subtype="success", is_error=False, text="report"):
    return {"type": "result", "subtype": subtype, "is_error": is_error, "result": text,
            "session_id": sid, "total_cost_usd": total}


def st(outcome, **kw):
    return dict({"ok": outcome != "anomaly", "anomalies": [{"kind": "x"}] if outcome == "anomaly" else [],
                 "outcome": outcome, "work": [], "waiting": []}, **kw)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "proj")
        self.feat = os.path.join(self.repo, ".mismagent", "features", "shop")
        os.makedirs(os.path.join(self.feat, "blocks", "orders", "todo"))
        open(os.path.join(self.feat, "building-blocks.yaml"), "w").write("blocks: []\n")
        open(os.path.join(self.feat, "blocks", "orders", "todo", "agg.md"), "w").write("# agg\n")
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e.x"], ["config", "user.name", "t"],
                     ["add", "."], ["commit", "-q", "-m", "seed"]):
            subprocess.run(["git", "-C", self.repo] + args, check=True, capture_output=True)
        self.plugin = os.path.join(self.tmp, "plugin")
        os.makedirs(os.path.join(self.plugin, "tools"))
        open(os.path.join(self.plugin, "tools", "mismagent.py"), "w").write(SIM_TOOL)
        self.claude = os.path.join(self.tmp, "claude")
        open(self.claude, "w").write(SIM_CLAUDE)
        os.chmod(self.claude, 0o755)
        self.set_status(st("work"))
        env = {"SIM_ROOT": self.tmp, "SIM_FEAT": self.feat, "SIM_REPO": self.repo}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        self.addCleanup(lambda: [os.environ.pop(k) if v is None else os.environ.__setitem__(k, v) for k, v in old.items()])

    def set_status(self, s):
        json.dump(s, open(os.path.join(self.feat, "sim-status.json"), "w"))

    def scenario(self, steps):
        json.dump(steps, open(os.path.join(self.tmp, "scenario.json"), "w"))

    def calls(self):
        p = os.path.join(self.tmp, "calls.log")
        return [json.loads(l) for l in open(p).read().splitlines()] if os.path.exists(p) else []

    def run_it(self, total=10, per=4, extra=()):
        args = ["--project", self.repo, "--feature", "shop", "--plugin-dir", self.plugin, "--total-usd", str(total),
                "--per-firing-usd", str(per), "--claude-bin", self.claude] + list(extra)
        return run.run(run.parse(args))

    def progress(self, i):
        return {"blocks/orders/todo/b%d.md" % i: "# b\n"}

    # ---------------------------------------------------------------------------------------------
    def test_resume_cumulative_costs_and_the_residual_cap(self):
        self.scenario([{"out": res(3.0), "write": self.progress(1)},
                       {"out": res(4.5), "write": self.progress(2)},
                       {"out": res(5.0), "status": st("done")}])
        out = self.run_it(total=5, per=4)
        self.assertEqual((out["outcome"], out["firings"], out["total_cost_usd"]), ("done", 3, 5.0))
        self.assertEqual([f["cost_usd"] for f in out["log"]], [3.0, 1.5, 0.5])        # deltas, not totals
        argv = [c["argv"] for c in self.calls()]
        caps = [a[a.index("--max-budget-usd") + 1] for a in argv]
        self.assertEqual(caps, ["4.0000", "2.0000", "0.5000"])                         # min(per, remaining)
        self.assertNotIn("--resume", argv[0])
        self.assertEqual([a[a.index("--resume") + 1] for a in argv[1:]], ["s-1", "s-1"])
        self.assertEqual(argv[0][:3], ["-p", "--plugin-dir", self.plugin])
        self.assertIn("--output-format", argv[0])
        self.assertEqual(argv[0][-1], "/mismagent:worker-composer shop")
        self.assertEqual({c["bg"] for c in self.calls()}, {"1"})
        self.assertEqual({c["cwd"] for c in self.calls()}, {self.repo})

    def test_total_budget_stops(self):
        self.scenario([{"out": res(4.0), "write": self.progress(1)}, {"out": res(8.0), "write": self.progress(2)}])
        out = self.run_it(total=8, per=4)
        self.assertEqual((out["outcome"], out["firings"]), ("budget", 2))

    def test_a_firing_out_of_budget_continues_while_total_remains(self):
        self.scenario([{"out": res(4.0, subtype="error_max_budget_usd", is_error=True), "code": 1,
                        "write": self.progress(1)},
                       {"out": res(5.0), "status": st("idle", waiting=["parked: agg"])}])
        out = self.run_it()
        self.assertEqual((out["outcome"], out["firings"]), ("idle", 2))

    def test_the_report_saying_done_is_not_believed(self):
        self.scenario([{"out": res(1.0, text="All blocks done. Feature complete."), "write": self.progress(1)},
                       {"out": res(2.0), "status": st("done")}])
        out = self.run_it()
        self.assertEqual((out["outcome"], out["firings"]), ("done", 2))
        self.assertEqual(out["log"][0]["status"], "work")

    def test_two_firings_without_structural_change_stop(self):
        self.scenario([{"out": res(1.0), "commit": {"block/agg": "v1"}},        # code: progress
                       {"out": res(2.0), "write": {"decisions.md": "x", "report.md": "firing 2"}},  # bookkeeping only
                       {"out": res(3.0), "commit": {"block/agg": None}},         # an empty commit: new tip, same tree
                       {"out": res(4.0)}])
        out = self.run_it()
        self.assertEqual((out["outcome"], out["firings"]), ("no-progress", 3))
        self.assertEqual([f["progress"] for f in out["log"]], [True, False, False])

    def test_code_on_a_block_branch_is_progress(self):
        self.scenario([{"out": res(1.0), "commit": {"block/agg": "v1"}},
                       {"out": res(2.0)},
                       {"out": res(3.0), "commit": {"block/agg": "v2"}},
                       {"out": res(4.0)}, {"out": res(5.0)}])
        out = self.run_it()
        self.assertEqual([f["progress"] for f in out["log"]], [True, False, True, False, False])
        self.assertEqual(out["outcome"], "no-progress")

    def test_cli_errors_stop_with_a_diagnostic(self):
        self.scenario([{"out": "Error: not logged in", "code": 1}])
        out = self.run_it()
        self.assertEqual((out["outcome"], out["firings"]), ("cli-error", 0))
        self.assertIn("not logged in", out["reason"])
        os.remove(os.path.join(self.tmp, "calls.log"))
        self.scenario([{"out": res(1.0, subtype="error_during_execution", is_error=True), "code": 1}])
        out = self.run_it()
        self.assertEqual((out["outcome"], out["firings"], out["total_cost_usd"]), ("cli-error", 1, 1.0))

    def test_missing_invalid_or_decreasing_cost_stops(self):
        for bad in (None, "1.0", True, float("nan")):
            if os.path.exists(os.path.join(self.tmp, "calls.log")):
                os.remove(os.path.join(self.tmp, "calls.log"))
            r = res(1.0)
            r["total_cost_usd"] = bad
            self.scenario([{"out": r}])
            self.assertEqual(self.run_it()["outcome"], "cost-invalid", bad)
        os.remove(os.path.join(self.tmp, "calls.log"))
        self.scenario([{"out": res(3.0), "write": self.progress(1)}, {"out": res(2.0)}])
        self.assertEqual(self.run_it()["outcome"], "cost-invalid")

    def test_status_is_read_before_the_first_firing(self):
        for outcome in ("done", "idle", "anomaly"):
            self.set_status(st(outcome))
            self.scenario([])
            out = self.run_it()
            self.assertEqual((out["outcome"], out["firings"]), (outcome, 0))
        self.assertEqual(self.calls(), [])

    def test_anomaly_after_a_firing_stops(self):
        self.scenario([{"out": res(1.0), "status": st("anomaly")}])
        self.assertEqual(self.run_it()["outcome"], "anomaly")

    def test_status_tool_error_stops(self):
        open(os.path.join(self.feat, "sim-status.json"), "w").write("not json")
        self.assertEqual(self.run_it()["outcome"], "status-error")

    def test_prompt_file_and_model(self):
        pf = os.path.join(self.tmp, "rules.md")
        open(pf, "w").write("Simulated user: answer from REQUISITI.md.\n")
        self.scenario([{"out": res(1.0), "status": st("done")}])
        self.run_it(extra=["--prompt-file", pf, "--model", "sonnet"])
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[-1], "/mismagent:worker-composer shop\n\nSimulated user: answer from REQUISITI.md.")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")

    def test_cli_version_below_the_minimum_is_refused(self):
        self.scenario([{"out": res(1.0), "status": st("done")}])
        for v, want in (("2.1.276 (Claude Code)", "cli-version"), ("garbage", "cli-version"),
                        ("2.1.277 (Claude Code)", "done"), ("2.2.0 (Claude Code)", "done")):
            if os.path.exists(os.path.join(self.tmp, "calls.log")):
                os.remove(os.path.join(self.tmp, "calls.log"))
            self.set_status(st("work"))
            os.environ["SIM_VERSION"] = v
            self.addCleanup(os.environ.pop, "SIM_VERSION", None)
            out = self.run_it()
            self.assertEqual(out["outcome"], want, v)
            if want == "cli-version":
                self.assertIn("2.1.277", out["reason"])
                self.assertEqual((out["firings"], self.calls()), (0, []))   # refused before any firing

    def test_uncommitted_worktree_work_and_evidence_content_are_progress(self):
        wt = os.path.join(self.repo, ".worktrees", "shop", "agg")
        subprocess.run(["git", "-C", self.repo, "worktree", "add", "-q", "-b", "block/agg", wt, "main"], check=True)
        self.scenario([{"out": res(1.0), "write": {"spikes/s.md": "v1"}},
                       {"out": res(2.0), "write": {"spikes/s.md": "v2"}},             # evidence content changed
                       {"out": res(3.0), "write": {"../../../.worktrees/shop/agg/code.txt": "x"}},   # uncommitted
                       {"out": res(4.0), "write": {"../../../.worktrees/shop/agg/code.txt": "y"}},
                       {"out": res(5.0), "write": {"../../../.worktrees/shop/agg/run.log": "z",
                                                   "../../../.worktrees/shop/agg/report.md": "r"}},  # bookkeeping
                       {"out": res(6.0)}])
        out = self.run_it(total=100)
        self.assertEqual([f["progress"] for f in out["log"]], [True, True, True, True, False, False])
        self.assertEqual(out["outcome"], "no-progress")

    def test_cli_main_prints_the_summary(self):
        self.scenario([{"out": res(1.0), "status": st("done")}])
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "run.py"), "--project", self.repo,
                            "--feature", "shop", "--plugin-dir", self.plugin, "--total-usd", "5",
                            "--per-firing-usd", "2", "--claude-bin", self.claude], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual((out["outcome"], out["firings"], out["total_cost_usd"]), ("done", 1, 1.0))


if __name__ == "__main__":
    unittest.main()
