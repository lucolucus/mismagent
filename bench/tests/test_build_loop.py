"""Tests for bench/build_loop.py — the simulated claude CLI of test_converse; the real CLI is never called.
Run: python3 -m unittest discover -s bench/tests -v"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_loop  # noqa: E402
from test_converse import ConverseTest, out, user  # noqa: E402


class BuildLoopTest(ConverseTest):
    def go(self, builder, users, *extra):
        json.dump(builder, open(os.path.join(self.root, "builder.json"), "w"))
        json.dump(users, open(os.path.join(self.root, "user.json"), "w"))
        a = build_loop.parse(["--project", self.repo, "--plugin-dir", self.root, "--release", "R0",
                              "--sim-file", os.path.join(self.root, "sim.md"), "--budget-usd", "10",
                              "--job-dir", os.path.join(self.root, "job"), "--claude", self.claude, *extra])
        return build_loop.run(a)

    # the inherited converse tests do not apply here
    test_released_after_question_and_confirm = test_no_progress_stops = None
    test_sim_stop_and_gap_counted = test_budget = test_invalid_sim_reply = None

    def test_confirm_then_tag(self):
        r = self.go([{"out": out(1.0, "ACTION: start 01\nNEXT: review"), "commit": True},
                     {"out": out(0.5, "ACTION: confirm R0\nNEEDS-HUMAN: confirm R0")},
                     {"out": out(0.2, "ACTION: confirm R0\nDONE: tagged"), "tag": "R0"}], [])
        self.assertEqual(r["outcome"], "released")
        calls = self.calls("builder")
        self.assertEqual(calls[0][-1], "/mismagent:build")
        self.assertEqual(calls[2][-1], "/mismagent:build --confirm R0")
        self.assertIn("--plugin-dir", calls[0])

    def test_blocked_slice_answered_by_sim_user(self):
        rel = ".mismagent/slices/doing/01-vendita.md"
        os.makedirs(os.path.join(self.repo, os.path.dirname(rel)))
        open(os.path.join(self.repo, rel), "w").write("Kind: feature\n\n## Question\nTurni?\n")
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", "q"], check=True)
        r = self.go([{"out": out(0.5, "NEEDS-HUMAN: %s" % rel)},
                     {"out": out(0.7, "ACTION: land 01"), "tag": "R0"}],
                    [user("answer", "Mattino, Pomeriggio, Sera")])
        self.assertEqual((r["outcome"], r["answers"]), ("released", 1))
        text = open(os.path.join(self.repo, rel)).read()
        self.assertIn("## Answer\nMattino, Pomeriggio, Sera", text)
        self.assertIn("Turni?", self.calls("user")[0][-1])

    def test_idle_and_other_release(self):
        r = self.go([{"out": out(0.3, "ACTION: idle\nNEXT: R1 needs /mismagent:specify")}], [])
        self.assertEqual(r["outcome"], "idle")


if __name__ == "__main__":
    unittest.main()
