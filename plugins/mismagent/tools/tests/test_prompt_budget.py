"""The prompt diet as a test: tools/budgets.json caps every operative prompt file, their total, the
skills' references/ (total and per file) and every frontmatter description. Run with the rest of the suite."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prompt_budget  # noqa: E402


class TestPromptBudget(unittest.TestCase):
    def test_budgets(self):
        r = prompt_budget.report()
        self.assertGreater(len(r["files"]), 30)  # the globs still find the plugins
        for where, msg in r["violations"]:
            with self.subTest(where=where):
                self.fail(msg)

    def test_an_over_budget_file_is_reported(self):
        b = prompt_budget.load_budgets()
        rel = sorted(b["files"])[0]
        b = dict(b, files=dict(b["files"], **{rel: 1}), description_chars=10 ** 6)
        self.assertIn(rel, [w for w, _ in prompt_budget.report(b)["violations"]])

    def test_an_over_budget_reference_is_reported(self):
        refs = prompt_budget.files(prompt_budget.REFERENCES)
        self.assertTrue(any("/craft/references/" in r for r in refs))  # the craft references ship
        b = dict(prompt_budget.load_budgets(), references_file=1, references_file_exceptions={})
        bad = [w for w, m in prompt_budget.report(b)["violations"] if "per-reference" in m]
        self.assertEqual(sorted(bad), refs)


if __name__ == "__main__":
    unittest.main()
