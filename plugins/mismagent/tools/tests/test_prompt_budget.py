"""The prompt diet as a test: tools/budgets.json caps every operative prompt file, their total, the
skills' references/ (total and per file) and every frontmatter description. Also: every `mm`
call the prompts name is a real subcommand (parsed, never executed). Run with the rest of the suite."""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prompt_budget  # noqa: E402

MM_SUBCOMMANDS = {"status", "next", "start", "park", "built", "review", "land", "gate", "tag", "check"}
# `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" <sub>` (may wrap), or the `MM <sub>` shorthand in code
MM_CALL = re.compile(r'(?:python3\s+"?\$\{CLAUDE_PLUGIN_ROOT\}/tools/mm\.py"?|(?:(?<=`)|(?<=^)|(?<=\n))'
                     r'[ \t]*MM)[ \t]+([A-Za-z][\w-]*)')


def mm_calls(text):
    return MM_CALL.findall(text)


class TestPromptBudget(unittest.TestCase):
    def test_budgets(self):
        r = prompt_budget.report()
        self.assertGreater(len(r["files"]), 0)  # the globs still find the plugin
        for where, msg in r["violations"]:
            with self.subTest(where=where):
                self.fail(msg)

    def test_an_over_budget_file_is_reported(self):
        b = prompt_budget.load_budgets()
        rel = sorted(prompt_budget.report(b)["files"])[0]
        b = dict(b, files=dict(b["files"], **{rel: 1}), description_chars=10 ** 6)
        self.assertIn(rel, [w for w, _ in prompt_budget.report(b)["violations"]])

    def test_an_uncapped_operative_file_is_an_error(self):
        b = prompt_budget.load_budgets()
        rel = sorted(prompt_budget.report(b)["files"])[0]
        caps = {k: v for k, v in b["files"].items() if k != rel}
        bad = prompt_budget.report(dict(b, files=caps))["violations"]
        self.assertTrue(any(w == rel and "no budget" in m for w, m in bad), bad)

    def test_a_capped_missing_file_is_not_yet_written(self):
        b = prompt_budget.load_budgets()
        ghost = "plugins/mismagent/skills/not-yet/SKILL.md"
        r = prompt_budget.report(dict(b, files=dict(b["files"], **{ghost: 10})))
        self.assertIn(ghost, r["not_yet_written"])
        self.assertNotIn(ghost, [w for w, _ in r["violations"]])

    def test_an_over_budget_reference_is_reported(self):
        refs = prompt_budget.files(prompt_budget.REFERENCES)
        self.assertTrue(any("/craft/references/" in r for r in refs))  # the craft references ship
        b = dict(prompt_budget.load_budgets(), references_file=1, references_file_exceptions={})
        bad = [w for w, m in prompt_budget.report(b)["violations"] if "per-reference" in m]
        self.assertEqual(sorted(bad), refs)


class TestDescriptionReader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def read(self, front):
        path = os.path.join(self.dir, "x.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n%s\n---\nbody\n" % front)
        return prompt_budget.description(path)  # an absolute path wins over REPO in os.path.join

    def test_plain_and_quoted(self):
        self.assertEqual(self.read("name: x\ndescription: plain words: here"), "plain words: here")
        self.assertEqual(self.read("description: 'it''s quoted'"), "it's quoted")
        self.assertEqual(self.read('description: "double quoted"\ntools: Read'), "double quoted")

    def test_missing_and_broken(self):
        self.assertIsNone(self.read("name: x"))
        with self.assertRaises(prompt_budget.FrontmatterError):
            self.read("description: 'never closed")


class TestMmSubcommands(unittest.TestCase):
    def test_parser(self):
        text = ('`MM` = `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py"`. Run `MM next --json`,\n'
                'then `python3\n   "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" gate`.\n'
                "MM land S1\nThe MM tool is prose.")
        self.assertEqual(mm_calls(text), ["next", "gate", "land"])

    def test_prompts_name_real_subcommands(self):
        for rel in prompt_budget.files(prompt_budget.OPERATIVE):
            with open(os.path.join(prompt_budget.REPO, rel), encoding="utf-8") as f:
                for sub in mm_calls(f.read()):
                    with self.subTest(file=rel, sub=sub):
                        self.assertIn(sub, MM_SUBCOMMANDS)


if __name__ == "__main__":
    unittest.main()
