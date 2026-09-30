"""Tests for the generated views (tools/generate-codex.py, tools/generate-pi.py): generated into a
temp dir, INSTALLED into a project path holding spaces, and every tool command they write is RUN
from a worker's worktree cwd — not only checked to exist in the repository.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(TOOLS)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_mismagent import SHELLS, run_in_shells  # noqa: E402

PLACEHOLDER = "@@MISMAGENT_SKILLS@@"
TEXT = (".md", ".toml")


def sh(*args, cwd=None):
    p = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        raise AssertionError("%s failed: %s%s" % (args, p.stdout[-400:], p.stderr[-400:]))
    return p.stdout


class ViewCase:  # a mixin: only the concrete views below are collected
    """Generate a view, install it, and look at the INSTALLED text."""
    view = None       # "codex" | "pi"
    installs = ()     # [(label, install.sh args relative to tmp, dirs holding the installed text)]

    @classmethod
    def setUpClass(cls):
        cls.tmp = os.path.realpath(tempfile.mkdtemp())
        cls.gen = os.path.join(cls.tmp, "generated %s view" % cls.view)
        sh(sys.executable, os.path.join(REPO, "tools", "generate-%s.py" % cls.view), "--out", cls.gen)
        cls.cwd = os.path.join(cls.tmp, "my project", ".worktrees", "shop", "agg-order")  # a worker's cwd
        os.makedirs(cls.cwd)
        cls.dirs = {}
        for label, args, dirs in cls.installs:
            sh("sh", os.path.join(cls.gen, "install.sh"), *[a.format(tmp=cls.tmp) for a in args])
            cls.dirs[label] = [d.format(tmp=cls.tmp) for d in dirs]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def texts(self, label):
        for d in self.dirs[label]:
            paths = [d] if os.path.isfile(d) else glob.glob(os.path.join(d, "**", "*"), recursive=True)
            for p in paths:
                if p.endswith(TEXT) and os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        yield p, f.read()

    def check_install(self, label, skills):
        bad, cmds = [], set()
        for p, text in self.texts(label):
            rel = os.path.relpath(p, self.tmp)
            bad += ["%s: %s" % (rel, t) for t in (PLACEHOLDER, "CLAUDE_PLUGIN_ROOT", "<plugin root>") if t in text]
            for m in re.finditer(r"python3\s+(\"[^\"\n]+\.py\"|\S+\.py)", text):
                cmds.add(m.group(0))
                if not m.group(1).startswith('"' + skills + "/"):
                    bad.append("%s: `%s` is not the quoted absolute installed path" % (rel, m.group(0)))
            rels = re.findall(r"\]\((?![a-z]+:|#)([^)#\s]+)", text) + re.findall(r"`(\.\.?/[^`\s]+)`", text)
            bad += ["%s: relative link %s does not resolve" % (rel, r) for r in rels  # the plugin's own layout
                    if not os.path.exists(os.path.join(os.path.dirname(p), r))]  # never survives install
            for m in re.finditer(re.escape(skills) + r"/([^\s`\"<]+)", text):  # every file reference resolves
                if not os.path.exists(os.path.join(skills, m.group(1).rstrip(".,;:)"))):
                    bad.append("%s: %s/%s does not exist" % (rel, skills, m.group(1)))
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertTrue(any("mismagent.py" in c for c in cmds) and any("board.py" in c for c in cmds), cmds)
        for cmd in sorted(cmds):  # from a worker's worktree, no plugin variable, bash and zsh
            for shell, rc, err in run_in_shells(cmd + " --help", self.cwd):
                self.assertEqual(rc, 0, "%s [%s]: %s" % (cmd, shell, err))

    def test_generated_tree_keeps_the_placeholder_quoted(self):
        for d, _, fns in os.walk(self.gen):
            for fn in fns:
                if fn.endswith(TEXT):
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        text = f.read()
                    self.assertNotIn("CLAUDE_PLUGIN_ROOT", text, fn)
                    for m in re.finditer(re.escape(PLACEHOLDER), text):
                        self.assertIn(text[m.start() - 1], "\"`", "%s: unquoted %s" % (fn, text[m.start():m.start() + 60]))

    def test_tool_ships_with_the_module_it_imports(self):
        scripts = os.path.join(self.gen, "skills", "mismagent-worker-composer", "scripts")
        self.assertEqual(sorted(os.listdir(scripts)), ["board.py", "mismagent.py"])

    def test_an_install_path_with_a_quote_is_refused(self):
        p = subprocess.run(["sh", os.path.join(self.gen, "install.sh"), os.path.join(self.tmp, 'bad"dir')],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


class TestCodexView(ViewCase, unittest.TestCase):
    view = "codex"
    installs = [("project", ["{tmp}/my project"],
                 ["{tmp}/my project/.agents/skills", "{tmp}/my project/.codex/agents", "{tmp}/my project/AGENTS.md"])]

    def test_project_install_runs_from_a_worktree(self):
        self.assertTrue(SHELLS)
        self.check_install("project", os.path.join(self.tmp, "my project", ".agents", "skills"))


    def test_an_install_path_breaking_the_toml_strings_is_refused(self):  # developer_instructions = '''...'''
        target = os.path.join(self.tmp, "it'''s")
        p = subprocess.run(["sh", os.path.join(self.gen, "install.sh"), target], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(os.path.join(target, ".codex")))  # refused before copying


class TestPiView(ViewCase, unittest.TestCase):
    view = "pi"
    installs = [("project", ["{tmp}/pi project"],
                 ["{tmp}/pi project/.agents/skills", "{tmp}/pi project/.pi", "{tmp}/pi project/AGENTS.md"]),
                ("package", ["--package", "{tmp}/pi package dir"], ["{tmp}/pi package dir"])]

    def test_project_install_runs_from_a_worktree(self):
        self.check_install("project", os.path.join(self.tmp, "pi project", ".agents", "skills"))

    def test_package_layout_runs_from_a_worktree(self):
        pkg = os.path.join(self.tmp, "pi package dir")
        self.assertEqual(sorted(os.listdir(pkg)), ["package.json", "prompts", "skills"])
        self.check_install("package", os.path.join(pkg, "skills"))


class TestCommittedViewsAreCurrent(unittest.TestCase):
    """codex/ and pi/ in the repo are exactly what the generators produce from the plugin now."""

    def test_views_match_a_fresh_generation(self):
        tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        stale = []
        for view in ("codex", "pi"):
            out = os.path.join(tmp, view)
            sh(sys.executable, os.path.join(REPO, "tools", "generate-%s.py" % view), "--out", out)
            p = subprocess.run(["diff", "-rq", out, os.path.join(REPO, view)], capture_output=True, text=True)
            if p.returncode:
                stale.append(p.stdout.replace(tmp, "<fresh>"))
        self.assertEqual(stale, [], "regenerate: python3 tools/generate-codex.py; python3 tools/generate-pi.py\n"
                         + "".join(stale))


if __name__ == "__main__":
    unittest.main()
