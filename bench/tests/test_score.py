"""Unit tests for bench/score.py on small synthetic runs in temp dirs (never the real runs)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import score  # noqa: E402

REQS = """# Requisiti
| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RF1.1 | Turno | 🔴 |
| RF1.2 | Cambio turno | 🟡 |
| RF1.10 | Altro | 🔴 |
| RF2.1 | Catalogo | 🔴 |
| RF2.2 | Attivi | 🟡 |
| RF2.3 | Carrello | 🟡 |
| RNF1 | DB | 🔴 |
| RB1 | Storico | |
"""

HEADING_LOG = """# MISMAGENT-LOG — Test (mismAgent v0.20)

## #1 — profile missing
- When: explore / step 0
- Class: profile

## #2 — manifest gap
- **When:** build-manifest, emitting blocks
- **Classification:** core-gap (no slice concept) — not a profile issue

## Movimento: build
### #3 — 🟡 ATTRITO (core, minore) — gate wrong
- Cosa: something

## #4 — mixed
- Quando / dove: model, architect
- Tipo: `core` (x) / `profilo` (y)

## #5 — odd
- When: wiring
- Classification: block bug

## 💡 Ideas
### IDEA-1 — not an entry
"""

TABLE_LOG = """# LOG
| # | Quando | Skill | Cosa si è inceppato | CORE/PROFILO | Fix |
|---|---|---|---|---|---|
| 1 | 2026-07-05, explore (Cassa) | x | y | PROFILO | z |
| 2 | 2026-07-09, model/architect | x | y | CORE | z |
| 3 | 2026-07-10, build | x | y | CORE + PROFILO | z |
"""


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "Run1")
        os.makedirs(self.root)
        write(self.root, "REQUISITI.md", REQS)

    def tearDown(self):
        self.tmp.cleanup()


class RequirementsTest(Base):
    def test_ids_and_priority(self):
        reqs = score.requirements(self.root)
        self.assertEqual(list(reqs), ["RF1.1", "RF1.2", "RF1.10", "RF2.1", "RF2.2", "RF2.3", "RNF1", "RB1"])
        self.assertEqual({i for i, h in reqs.items() if h}, {"RF1.1", "RF1.10", "RF2.1", "RNF1"})

    def test_citations_exact_wildcard_range(self):
        reqs = score.requirements(self.root)
        self.assertEqual(score.cited("see RF1.1. and RF1.10", reqs), {"RF1.1", "RF1.10"})
        self.assertEqual(score.cited("XRF1.1 RF1.1x9 RF9.9", reqs), set())
        self.assertEqual(score.cited("covers RF1.*", reqs), {"RF1.1", "RF1.2", "RF1.10"})
        self.assertEqual(score.cited("RF2.1–RF2.3", reqs), {"RF2.1", "RF2.2", "RF2.3"})
        self.assertEqual(score.cited("RF2.1-2.2", reqs), {"RF2.1", "RF2.2"})


class FrictionTest(unittest.TestCase):
    def test_heading_format(self):
        es = score.parse_friction(HEADING_LOG)
        self.assertEqual([e["id"] for e in es], [1, 2, 3, 4, 5])
        self.assertEqual([e["class"] for e in es], ["profile", "core", "core", "both", "unclassified"])
        self.assertEqual([e["movement"] for e in es], ["explore", "model", "build", "model", None])

    def test_table_format(self):
        es = score.parse_friction(TABLE_LOG)
        self.assertEqual([(e["class"], e["movement"]) for e in es],
                         [("profile", "explore"), ("core", "model"), ("both", "build")])


class RunTest(Base):
    def build_run(self):
        r = self.root
        write(r, "MISMAGENT-LOG.md", HEADING_LOG)
        write(r, "src/main/kotlin/a/Turno.kt", "// RF1.1\nclass Turno\n\nfun x() = 1\n")
        write(r, "src/desktopTest/kotlin/a/TurnoTest.kt",
              "// RF1.1 RNF1\nclass TurnoTest {\n  @Test fun `a`() {}\n  @Test fun `b`() {}\n}\n")
        write(r, "src/test/kotlin/a/Helper.kt", "object Helper\n")
        write(r, "tests/test_x.py", "def test_one():\n    pass\n\ndef test_two():\n    pass\n")
        write(r, "build/generated/Gen.kt", "@Test fun ignored() {}\n")
        write(r, ".mismagent/features/f/building-blocks.yaml", "blocks: [{req: RF2.1}]\n")
        write(r, ".mismagent/features/f/tactical-model.md", "RF1.2 RF1.1\n")
        write(r, ".mismagent/features/f/blocks/ctx/todo/b1.md", "x")
        write(r, ".mismagent/features/f/blocks/ctx/done/b2.md", "x")
        write(r, ".mismagent/features/f/blocks/ctx/done/b3.md", "x")
        write(r, ".mismagent/features/f/open-questions/b1.md", "q")
        write(r, ".mismagent/features/f/integrated/b2.json", "{}")
        write(r, ".mismagent/features/f/rework/b3-1.md", "r")
        write(r, ".mismagent/features/f/decisions.md", "# D\n### D-0001 — a\n### D-0002 — b\n")
        write(r, ".mismagent/decisions/0001-stack.md", "adr")
        return r

    def test_full_score(self):
        plugins = os.path.join(self.tmp.name, "plugins.json")
        write(self.tmp.name, "plugins.json", json.dumps({"plugins": {"mismagent@m": [
            {"projectPath": self.root, "installPath": "/c/mismagent/0.20.0"}]}}))
        s = score.score(self.build_run(), plugins)
        self.assertEqual(s["version"], "plugin 0.20.0 · log 0.20")
        self.assertEqual((s["test_files"], s["test_cases"]), (2, 4))
        self.assertEqual(s["test_cases_by_lang"], {"Kotlin": 2, "Python": 2})
        self.assertEqual(s["main_loc"], 3)
        self.assertEqual(s["req_model"], ["RF1.1", "RF1.2", "RF2.1"])
        self.assertEqual(s["req_tests"], ["RF1.1", "RNF1"])
        self.assertEqual(s["req_main"], ["RF1.1"])
        self.assertEqual(s["req_high_tests"], {"covered": 2, "of": 4})
        self.assertEqual(s["friction"]["entries"], 5)
        p = s["process"]
        self.assertEqual((p["blocks"]["todo"], p["blocks"]["done"]), (1, 2))
        self.assertEqual((p["open_questions"], p["rework"], p["integrated"]), (1, 1, 1))
        self.assertEqual((p["decision_notes"], p["adrs"]), (2, 1))
        self.assertTrue(score.is_na(s["git"]))

    def test_empty_run_is_na_not_zero(self):
        s = score.score(self.root, os.path.join(self.tmp.name, "none.json"))
        for k in ("version", "test_cases", "main_loc", "req_model", "req_tests", "friction", "process"):
            self.assertTrue(score.is_na(s[k]), k)
        with redirect_stdout(io.StringIO()) as out:
            score.main([self.root, "--plugins-json", os.path.join(self.tmp.name, "none.json")])
        self.assertIn("| test cases | n/a |", out.getvalue())

    def test_git(self):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull)
        run = lambda *a: subprocess.run(["git", "-C", self.root] + list(a), check=True, env=env,
                                        capture_output=True)
        run("init", "-q", "-b", "main")
        g = score.git_stats(self.root)
        self.assertEqual(g["commits"], 0)
        self.assertTrue(score.is_na(g["span_days"]))
        run("add", "-A")
        run("commit", "-q", "-m", "first")
        run("branch", "other")
        g = score.git_stats(self.root)
        self.assertEqual((g["commits"], g["branches"], g["span_days"]), (1, 2, 0))

    def test_json_output(self):
        self.build_run()
        with redirect_stdout(io.StringIO()) as out:
            score.main([self.root, "--json", "--plugins-json", os.devnull])
        data = json.loads(out.getvalue())
        self.assertEqual(data[0]["run"], "Run1")
        self.assertIn("n/a", data[0]["gate"])


if __name__ == "__main__":
    unittest.main()
