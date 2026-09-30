"""Tests for bench/converse.py — a SIMULATED claude CLI; the real CLI is never called.
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
import converse  # noqa: E402

# The fake `claude`: a call with `--tools` is the simulated user, any other the builder. Each pops its
# own next scripted step; a builder step may commit or tag in the project.
SIM_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
root = os.environ["SIM_ROOT"]; role = "user" if "--tools" in sys.argv else "builder"
steps = json.load(open(os.path.join(root, role + ".json")))
log = os.path.join(root, role + ".log")
n = len(open(log).read().splitlines()) if os.path.exists(log) else 0
open(log, "a").write(json.dumps(sys.argv[1:]) + "\n")
if n >= len(steps):
    print("scenario exhausted"); sys.exit(3)
s = steps[n]; repo = os.environ["SIM_REPO"]
if s.get("commit"):
    open(os.path.join(repo, "f%d.txt" % n), "w").write("x")
    subprocess.run(["git", "-C", repo, "add", "."], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "work"], check=True)
if s.get("tag"):
    subprocess.run(["git", "-C", repo, "tag", s["tag"]], check=True)
print(json.dumps(s["out"]))
'''


def out(total, text="ok", sid="s-1", subtype="success"):
    return {"total_cost_usd": total, "result": text, "session_id": sid, "subtype": subtype}


def user(kind, message="Va bene, prosegui.", gap=False, cost=0.01):
    return {"out": out(cost, json.dumps({"kind": kind, "message": message, "gap": gap}))}


class ConverseTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "repo"); os.makedirs(self.repo)
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"], check=True)
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            subprocess.run(["git", "-C", self.repo, "config", k, v], check=True)
        open(os.path.join(self.repo, "REQUISITI.md"), "w").write("# req\n")
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", "init"], check=True)
        self.claude = os.path.join(self.root, "claude")
        open(self.claude, "w").write(SIM_CLAUDE); os.chmod(self.claude, 0o755)
        for name, text in (("open.md", "Ciao"), ("sim.md", "You are the user")):
            open(os.path.join(self.root, name), "w").write(text)
        os.environ.update(SIM_ROOT=self.root, SIM_REPO=self.repo)

    def tearDown(self):
        shutil.rmtree(self.root)

    def go(self, builder, users, *extra):
        json.dump(builder, open(os.path.join(self.root, "builder.json"), "w"))
        json.dump(users, open(os.path.join(self.root, "user.json"), "w"))
        a = converse.parse(["--project", self.repo, "--phase", "B", "--tag", "R0", "--goal", "R0",
                            "--opening-file", os.path.join(self.root, "open.md"),
                            "--sim-file", os.path.join(self.root, "sim.md"), "--budget-usd", "10",
                            "--job-dir", os.path.join(self.root, "job"), "--claude", self.claude, *extra])
        return converse.run(a)

    def calls(self, role):
        p = os.path.join(self.root, role + ".log")
        return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

    def test_released_after_question_and_confirm(self):
        r = self.go([{"out": out(1.0, "Domanda: quali turni?"), "commit": True},
                     {"out": out(2.5, "R0 completa, test verdi."), "commit": True},
                     {"out": out(3.0, "Tag creato."), "tag": "R0"}],
                    [user("answer", "Mattino, Pomeriggio, Sera"), user("confirm", "Confermo R0")])
        self.assertEqual(r["outcome"], "released")
        self.assertEqual((r["turns"], r["questions"]), (3, 1))
        self.assertAlmostEqual(r["builder_usd"], 3.0)          # cumulative totals → deltas
        self.assertAlmostEqual(r["total_cost_usd"], 3.02)
        b = self.calls("builder")
        self.assertNotIn("--resume", b[0])
        self.assertEqual(b[1][b[1].index("--resume") + 1], "s-1")
        self.assertEqual(b[1][-1], "Mattino, Pomeriggio, Sera")   # the user's answer is the next message
        self.assertIn("Domanda: quali turni?", self.calls("user")[0][-1])

    def test_no_progress_stops(self):
        r = self.go([{"out": out(0.5)}, {"out": out(1.0)}, {"out": out(1.5)}],
                    [user("continue"), user("continue"), user("continue")])
        self.assertEqual(r["outcome"], "no-progress")

    def test_sim_stop_and_gap_counted(self):
        r = self.go([{"out": out(0.5), "commit": True}, {"out": out(1.0), "commit": True}],
                    [user("answer", "boh", gap=True), user("stop", "bloccato")])
        self.assertEqual((r["outcome"], r["policy_gaps"]), ("sim-stop", 1))

    def test_budget(self):
        r = self.go([{"out": out(9.99), "commit": True}], [])
        self.assertEqual(r["outcome"], "budget")

    def test_invalid_sim_reply(self):
        r = self.go([{"out": out(0.5), "commit": True}], [{"out": out(0.01, "not json")}])
        self.assertEqual(r["outcome"], "cli-error")


if __name__ == "__main__":
    unittest.main()
