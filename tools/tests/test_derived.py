"""Tests for the derived packagings (tools/generate-codex.py, tools/generate-pi.py) — stdlib
unittest; each runtime is generated, installed into a fresh git project, and its mm.py run there.
Run: python3 -m unittest discover -s tools/tests -v"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


def sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout


class Packaging:
    """One runtime: generated into a temp dir, installed into a project whose path has a space."""
    runtime, specify = None, None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, self.runtime)
        self.project = os.path.join(self.tmp.name, "a project")
        sh([sys.executable, os.path.join(TOOLS, "generate-%s.py" % self.runtime), "--out", self.out])
        os.makedirs(self.project)
        sh(["git", "init", "-q"], self.project)
        sh(["sh", os.path.join(self.out, "install.sh"), self.project])
        sh(GIT + ["commit", "-q", "--allow-empty", "-m", "init"], self.project)
        self.mm = os.path.join(self.project, ".agents", "skills", "mismagent-build", "scripts", "mm.py")

    def tearDown(self):
        self.tmp.cleanup()

    def installed_text(self):
        for d, _, fns in os.walk(self.project):
            if "/.git" not in d:
                for fn in fns:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        yield os.path.join(d, fn), f.read()

    def test_every_path_is_anchored_to_the_installation(self):
        for path, text in self.installed_text():
            self.assertNotIn("@@MISMAGENT_SKILLS@@", text, path)

    def test_the_build_names_the_installed_mm(self):
        with open(os.path.join(self.project, ".agents", "skills", "mismagent-build", "SKILL.md"),
                  encoding="utf-8") as f:
            self.assertIn('"%s"' % self.mm, f.read())

    def test_mm_runs_from_the_project_with_the_runtime_names(self):
        action = json.loads(sh([sys.executable, self.mm, "next", "--json"], self.project))
        self.assertEqual(action["action"], "idle")
        self.assertIn(self.specify, action["reason"])

    def test_mm_reads_its_settings_from_agents_md(self):
        os.makedirs(os.path.join(self.project, ".mismagent", "slices", "todo"))
        with open(os.path.join(self.project, ".mismagent", "slices", "todo", "01-a.md"), "w") as f:
            f.write("# 01-a\nrelease: R0\n")
        action = json.loads(sh([sys.executable, self.mm, "next", "--json"], self.project))
        self.assertEqual(action["action"], "skeleton")
        self.assertIn("AGENTS.md", action["reason"])

    def test_reinstalling_removes_a_retired_piece(self):
        stale = os.path.join(self.project, ".agents", "skills", "mismagent-worker-composer")
        os.makedirs(stale)
        sh(["sh", os.path.join(self.out, "install.sh"), self.project])
        self.assertFalse(os.path.exists(stale))


class Codex(Packaging, unittest.TestCase):
    runtime, specify = "codex", "$mismagent-specify"


class Pi(Packaging, unittest.TestCase):
    runtime, specify = "pi", "/skill:mismagent-specify"


if __name__ == "__main__":
    unittest.main()
