"""What the prompts must get right, as a test: every frontmatter is readable with a description
within its cap, and every `mm` call the prompts name is a real subcommand (parsed, never executed).
No word caps. Run with the rest of the suite."""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prompt_lint  # noqa: E402

MM_SUBCOMMANDS = {"status", "next", "start", "park", "built", "review", "land", "gate", "tag", "check", "shot", "log"}
# `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" <sub>` (may wrap), or the `MM <sub>` shorthand in code
MM_CALL = re.compile(r'(?:python3\s+"?\$\{CLAUDE_PLUGIN_ROOT\}/tools/mm\.py"?|(?:(?<=`)|(?<=^)|(?<=\n))'
                     r'[ \t]*MM)[ \t]+([A-Za-z][\w-]*)')


def mm_calls(text):
    return MM_CALL.findall(text)


class TestPromptLint(unittest.TestCase):
    def test_no_violations(self):
        r = prompt_lint.report()
        self.assertGreater(len(r["files"]), 0)  # the globs still find the plugin
        for where, msg in r["violations"]:
            with self.subTest(where=where):
                self.fail(msg)


class TestDescriptionReader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def read(self, front):
        path = os.path.join(self.dir, "x.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n%s\n---\nbody\n" % front)
        return prompt_lint.description(path)  # an absolute path wins over REPO in os.path.join

    def test_plain_and_quoted(self):
        self.assertEqual(self.read("name: x\ndescription: plain words: here"), "plain words: here")
        self.assertEqual(self.read("description: 'it''s quoted'"), "it's quoted")
        self.assertEqual(self.read('description: "double quoted"\ntools: Read'), "double quoted")

    def test_missing_and_broken(self):
        self.assertIsNone(self.read("name: x"))
        with self.assertRaises(prompt_lint.FrontmatterError):
            self.read("description: 'never closed")


class TestMmSubcommands(unittest.TestCase):
    def test_parser(self):
        text = ('`MM` = `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py"`. Run `MM next --json`,\n'
                'then `python3\n   "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" gate`.\n'
                "MM land S1\nThe MM tool is prose.")
        self.assertEqual(mm_calls(text), ["next", "gate", "land"])

    def test_prompts_name_real_subcommands(self):
        for rel in prompt_lint.files(prompt_lint.OPERATIVE):
            with open(os.path.join(prompt_lint.REPO, rel), encoding="utf-8") as f:
                for sub in mm_calls(f.read()):
                    with self.subTest(file=rel, sub=sub):
                        self.assertIn(sub, MM_SUBCOMMANDS)


if __name__ == "__main__":
    unittest.main()
