"""Tests for tools/mmsite.py — stdlib unittest; the page is built from a temporary git repository.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -p 'test_mmsite.py' -v"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import mmsite  # noqa: E402

STORM = """# Event storm

## Timeline
| # | event | command | actor | policy | read model | undo |
|---|---|---|---|---|---|---|
| 1 | File opened | open | user | show it | doc | – |
| 2 | Signature checked | – | system | colour it | badge | – |

## Hotspots
- H1: revocation rules — user
"""
BRIEF = "# Brief\n\n- S1 one program\n- S2 no network\n\n**R1 — the Mac app**\n- open and read\n\n**R2 — export**\n"
EXAMPLES = """| id | given | when | then | rule | req | release |
|---|---|---|---|---|---|---|
| EX-1 | a file | I open it | it shows | shown at once | event 1-2, S1 | R1 |
| EX-2 | a file | I open it | old (superseded by EX-1) | x | decision 0001 | R1 |
"""


class Expand(unittest.TestCase):
    def test_reads_events_ranges_codes_and_decisions(self):
        self.assertEqual(mmsite.expand("event 1-3"), ["event:1", "event:2", "event:3"])
        self.assertEqual(mmsite.expand("1, S12"), ["event:1", "code:S12"])
        self.assertEqual(mmsite.expand("F0–F2"), ["code:F0", "code:F1", "code:F2"])
        self.assertEqual(mmsite.expand("E6, decision 0005"), ["decision:0005", "code:E6"])

    def test_ignores_releases_and_examples(self):
        self.assertEqual(mmsite.expand("8, R3, EX-4"), ["event:8"])


class Page(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        files = {".mismagent/event-storm.md": STORM, ".mismagent/brief.md": BRIEF,
                 ".mismagent/examples/open.md": EXAMPLES,
                 ".mismagent/decisions/0001-stack.md": "# 0001 — Stack\n",
                 ".mismagent/slices/done/01-open.md": "Kind: feature\nRelease: R1\nExamples: EX-1\n\nOpen a file.\n\n## Progress\n- done it\n",
                 ".mismagent/reviews/01-open-1.md": "VERDICT: PASS\nSHA: abcdef1\nSCORES: simple=5 naming=4\n\nfine\n",
                 "tests/acceptance/open_test.py": "# EX-1\n",
                 ".claude/skills/conventions/SKILL.md": "# conventions\n"}
        for rel, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(self.dir, rel)), exist_ok=True)
            with open(os.path.join(self.dir, rel), "w", encoding="utf-8") as f:
                f.write(text)
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t",
                                                    "commit", "-qm", "mm land 01-open"]):
            subprocess.run(["git", *cmd], cwd=self.dir, check=True)

    def data(self):
        out = os.path.join(self.dir, "page.html")
        subprocess.run([sys.executable, os.path.join(TOOLS, "mmsite.py"), "--out", out], cwd=self.dir,
                       check=True, capture_output=True)
        with open(out, encoding="utf-8") as f:
            page = f.read()
        return json.loads(re.search(r"const DATA = (.*?);\n", page).group(1).replace("<\\/", "</"))

    def test_releases_come_from_the_brief_even_without_slices(self):
        d = self.data()
        self.assertEqual([(r["id"], r["title"]) for r in d["releases"]], [("R1", "the Mac app"), ("R2", "export")])

    def test_a_slice_carries_its_progress_review_and_landing(self):
        s = self.data()["slices"][0]
        self.assertEqual((s["stem"], s["state"], s["examples"]), ("01-open", "done", ["EX-1"]))
        self.assertIn("done it", s["progress"])
        self.assertEqual(s["reviews"][0]["scores"], {"simple": "5", "naming": "4"})
        self.assertTrue(s["landed"])

    def test_requirements_link_to_examples_slices_and_tests(self):
        d = self.data()
        ex = {e["id"]: e for e in d["examples"]}
        self.assertEqual(ex["EX-1"]["reqs"], ["event:1", "event:2", "code:S1"])
        self.assertEqual((ex["EX-1"]["slices"], ex["EX-1"]["tests"]), (["01-open"], ["tests/acceptance/open_test.py"]))
        self.assertEqual(ex["EX-2"]["superseded"], "EX-1")
        reqs = {r["id"]: r for r in d["requirements"]}
        self.assertEqual(reqs["event:2"]["label"], "#2 Signature checked")
        self.assertEqual(reqs["code:S2"]["text"], "S2 no network")  # the cited family is listed whole
        self.assertEqual(reqs["code:H1"]["group"], "hotspot")
        self.assertEqual(reqs["decision:0001"]["text"], "0001 — Stack")


if __name__ == "__main__":
    unittest.main()
