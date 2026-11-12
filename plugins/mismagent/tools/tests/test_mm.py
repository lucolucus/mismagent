"""Tests for tools/mm.py — stdlib unittest; each test runs mm in a temporary git repository.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -p 'test_mm.py' -v"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

MM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mm.py")

CLAUDE = ("# Project\n\n## mismagent\n- test: true\n-   lint :  `true`\n- smoke: true\n- max_file_lines: 400\n\n"
          "## Other\n- test: false\n")
EXAMPLES = """# Examples

| id | given | when | then | rule | req | release |
|----|-------|------|------|------|-----|---------|
| EX-1 | a cart | add | 1 item | R | Q1 | R0 |
|EX-2|a cart|remove|0 items|R|Q1|R0|
| EX-3 | x | y | z | R | Q2 | R1 |
"""


def slice_text(kind="feature", release="R0", examples="EX-1", extra=""):
    return "# Slice\n\nKind: %s\nRelease: %s\nExamples: %s\n\n## Goal\nDo it.\n%s" % (
        kind, release, examples, extra)


def parse_base(text):
    return re.search(r"^Base: (\w+)", text, re.M).group(1)


class Repo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mm-test-")
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.write("CLAUDE.md", CLAUDE)
        self.write(".mismagent/examples/cart.md", EXAMPLES)
        self.write("ARCHITECTURE.md", "# Architecture\n")
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\n")
        self.commit("init")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    # helpers
    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True,
                              check=True).stdout.strip()

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, rel):
        with open(os.path.join(self.dir, rel), encoding="utf-8") as f:
            return f.read()

    def commit(self, msg="work"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.head()

    def head(self):
        return self.git("rev-parse", "HEAD")

    def mm(self, *args, cwd=None, env=None):
        p = subprocess.run([sys.executable, MM, *args], cwd=cwd or self.dir, capture_output=True,
                           text=True, env=env)
        return p.returncode, p.stdout, p.stderr

    def next(self):
        code, out, err = self.mm("next", "--json")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def slice(self, name, state="todo", **kw):
        self.write(".mismagent/slices/%s/%s.md" % (state, name), slice_text(**kw))

    def review(self, name, verdict, sha=None):
        self.write(".mismagent/reviews/%s.md" % name,
                   "# Review\nVERDICT: %s\nSHA: %s\n" % (verdict, (sha or self.head())[:9]))

    def work(self, stem="01-cart", code="x = 1\n", msg="code"):
        """Builder work: code plus the progress entry, committed."""
        self.write("src/cart.py", code)
        sha = self.commit(msg)
        if os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/%s.md" % stem)):
            code, _, err = self.mm("built", stem, "--friction", "none")
            self.assertEqual(code, 0, err)
            sha = self.head()
        return sha

    def acceptance(self, rel, text):
        self.write("tests/acceptance/" + rel, text)

    def started(self, name="01-cart", **kw):
        """A slice in doing via mm start, its examples' markers in place (mm built checks them)."""
        self.slice(name, **kw)
        self.acceptance("test_%s.py" % name, "# %s\n" % kw.get("examples", "EX-1").split("\n")[0])
        self.commit("plan")
        code, _, err = self.mm("start", name)
        self.assertEqual(code, 0, err)

    def done_release(self, release="R0"):
        """All slices of a release done (with acceptance markers), committed."""
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(release=release, examples="EX-1, EX-2").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "def test_ex1():  # EX-1\n    pass\n\ndef test_ex2():  # EX-2\n    pass\n")
        self.commit("done")

    def check(self, *args):
        return self.mm("check", *args)

    def counting(self, lint="true"):
        """A `test:` that counts its runs outside the tree; -> the count so far."""
        self.write("CLAUDE.md", "## mismagent\n- test: echo run >> .git/runs; seq 1 40; echo test_cart PASSED\n"
                   "- lint: %s\n" % lint)
        self.commit("gate")
        return lambda: len(self.read(".git/runs").split()) if os.path.exists(os.path.join(self.dir, ".git/runs")) else 0

    def forget_gate(self):
        shutil.rmtree(os.path.join(self.dir, ".git", "mismagent.gate"), ignore_errors=True)

    def fake_git(self, sub, action, once=True):
        """A git on PATH that runs `action` (sh) before the first (or every) `git <sub>`; -> the env."""
        real, mark = shutil.which("git"), os.path.join(self.dir, ".git", "fakebin", "fired")  # under .git/: no dirt
        guard = ' && [ ! -e "%s" ] && { : > "%s"; true; }' % (mark, mark) if once else ""
        self.write(".git/fakebin/git", "#!/bin/sh\nsub=\"$1\"; [ \"$sub\" = \"--literal-pathspecs\" ] && sub=\"$2\"\n"
                   "if [ \"$sub\" = \"%s\" ]%s; then\n  %s\nfi\nexec \"%s\" \"$@\"\n" % (sub, guard, action, real))
        os.chmod(os.path.join(self.dir, ".git", "fakebin", "git"), 0o755)
        return dict(os.environ, PATH=os.path.join(self.dir, ".git", "fakebin") + os.pathsep + os.environ["PATH"])

    def beside(self, msg="01-cart: beside", once=True):
        """A raw commit by someone else while mm builds its tree (at `git write-tree`)."""
        return self.fake_git("write-tree", 'env -u GIT_INDEX_FILE "%s" commit -q --allow-empty -m "%s"'
                             % (shutil.which("git"), msg), once)


class Parsing(Repo):
    def test_examples_and_slice_parsing(self):
        self.slice("01-cart", examples="EX-1,  EX-2")
        self.slice("02-other", kind="refactor", release="R1", examples="")
        self.commit()
        code, out, err = self.mm("status", "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data["slices"]["todo"], ["01-cart", "02-other"])
        self.assertEqual(list(data["releases"]), ["R0", "R1"])
        self.assertEqual(data["releases"]["R0"]["todo"], 1)
        self.assertEqual(data["missing_acceptance"], ["EX-1", "EX-2", "EX-3"])
        self.assertEqual(data["example_errors"], [])
        self.assertEqual(self.check()[0], 0)

    def test_status_markers_notes_superseded(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES +
                   "| EX-4 | x | y | nothing (superseded by EX-3) | R | Q | R1 |\n")
        self.acceptance("test_a.py", "# EX-1\n# EX-9\n# noqa: E501\n")
        self.write(".mismagent/design-notes.md", "# Notes\n- one\n- two\nnot a note\n")
        code, out, _ = self.mm("status", "--json")
        data = json.loads(out)
        self.assertEqual(data["missing_acceptance"], ["EX-2", "EX-3"])
        self.assertEqual(data["superseded"], ["EX-4"])
        self.assertEqual(list(data["unknown_markers"]), ["EX-9"])
        self.assertEqual(data["notes"], 2)
        code, out, _ = self.mm("status")
        self.assertEqual(code, 0)
        self.assertIn("superseded examples: EX-4", out)
        self.assertIn("design notes: 2", out)

    def test_release_order_examples_then_slices(self):
        self.slice("01-a", release="CR1", examples="")
        code, out, _ = self.mm("status", "--json")
        self.assertEqual(list(json.loads(out)["releases"]), ["R0", "R1", "CR1"])

    def test_help_and_usage(self):
        for sub in ("status", "next", "start", "land", "gate", "tag", "check", "conventions", "designed"):
            self.assertEqual(self.mm(sub, "--help")[0], 0, sub)
        self.assertEqual(self.mm()[0], 2)
        self.assertEqual(self.mm("bogus")[0], 2)
        self.assertEqual(self.mm("start")[0], 2)

    def test_runs_from_subdirectory(self):
        os.makedirs(os.path.join(self.dir, "src/deep"))
        code, out, _ = self.mm("next", cwd=os.path.join(self.dir, "src/deep"))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("idle — "), out)


class Next(Repo):
    def test_blocked_then_answered(self):
        self.started(extra="\n## Question\nWhich currency?\n\n## Answer\n\n")
        self.assertEqual(self.next()["action"], "blocked")
        path = ".mismagent/slices/doing/01-cart.md"
        self.write(path, self.read(path) + "EUR only.\n")
        self.commit("answer")
        d = self.next()
        self.assertEqual(d["action"], "build")  # an answer is not work: only .mismagent/ changed
        self.assertEqual(d["slice"], "01-cart")

    def test_build_resume_review(self):
        self.started()
        d = self.next()
        self.assertEqual((d["action"], d["slice"]), ("build", "01-cart"))
        self.write("src/cart.py", "x = 1\n")
        self.assertEqual(self.next()["action"], "resume")
        self.commit("code")
        d = self.next()  # committed work but no progress entry: the builder was cut
        self.assertEqual(d["action"], "resume")
        self.assertIn("no `Built: 1` in .mismagent/slices/doing/01-cart.md", d["reason"])
        self.assertEqual(self.mm("built", "01-cart", "--friction", "none")[0], 0)
        self.assertIn("Built: 1", self.read(".mismagent/slices/doing/01-cart.md"))
        self.assertEqual(self.next()["action"], "review")
        code, out, _ = self.mm("next")
        self.assertTrue(out.startswith("review 01-cart — "), out)

    def test_a_builder_cut_in_a_rework_resumes(self):
        self.started()
        self.work()
        self.review("01-cart-1", "REWORK")
        self.assertEqual(self.next()["action"], "rework")
        self.write("src/cart.py", "x = 2\n")
        self.commit("half the fix")  # cut before mm built
        d = self.next()
        self.assertEqual(d["action"], "resume")
        self.assertIn("no `Built: 2`", d["reason"])
        self.assertEqual(self.mm("built", "01-cart", "--friction", "none")[0], 0)
        self.assertEqual(self.next()["action"], "review")

    def test_built_runs_the_base_check_before_the_suite(self):
        self.slice("01-cart")  # no acceptance marker for EX-1 yet
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: touch suite-ran"))
        self.commit("plan")
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.write("src/cart.py", "x = 1\n")
        head = self.commit("code")
        code, out, _ = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 1)
        self.assertIn("error: .mismagent/slices/doing/01-cart.md: doing, but EX-1 has no acceptance marker", out)
        self.assertIn("test: not run (check red)", out)
        self.assertEqual(out.strip().splitlines()[-1], "gate: red (check)")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "suite-ran")))  # a red check is not worth a suite run
        self.assertEqual(self.head(), head)
        self.assertNotIn("Built:", self.read(".mismagent/slices/doing/01-cart.md"))
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("acc")
        code, out, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "suite-ran")))

    def test_built_refuses_a_base_that_is_not_an_ancestor(self):
        self.started()
        self.git("checkout", "-q", "-b", "side")
        side = self.commit("side")
        self.git("checkout", "-q", "-")
        path = ".mismagent/slices/doing/01-cart.md"
        self.write(path, re.sub(r"^Base: .*$", "Base: " + side, self.read(path), flags=re.M))
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        self.assertIn("Base %s is not an ancestor of HEAD" % side[:12], self.mm("built", "01-cart", "--friction", "none")[2])

    def test_built_preconditions(self):
        self.slice("01-cart")
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("plan")
        self.assertIn("not doing", self.mm("built", "01-cart", "--friction", "none")[2])
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.assertIn("nothing built since mm start", self.mm("built", "01-cart", "--friction", "none")[2])
        self.write("src/cart.py", "x = 1\n")
        self.assertIn("dirty", self.mm("built", "01-cart", "--friction", "none")[2])
        self.commit("code")
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: false"))
        self.commit("red")
        code, out, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual((code, out.strip().splitlines()[-1]), (1, "gate: red (test)"))
        self.assertNotIn("Built:", self.read(".mismagent/slices/doing/01-cart.md"))
        self.write("CLAUDE.md", CLAUDE)
        self.commit("green")
        self.assertEqual(self.mm("built", "01-cart", "--friction", "none")[0], 0)
        self.review("01-cart-1", "REWORK")
        self.assertIn("review 1 is at HEAD", self.mm("built", "01-cart", "--friction", "none")[2])

    def test_land_on_pass_at_head(self):
        self.started()
        self.commit("code")
        self.review("01-cart-1", "PASS")
        self.write(".mismagent/design-notes.md", "- a note\n")  # reviewer output: not dirty
        self.assertEqual(self.next()["action"], "land")

    def test_review_at_old_sha_does_not_count(self):
        self.started()
        old = self.work()
        self.review("01-cart-1", "PASS", sha=old)
        self.work(code="x = 2\n", msg="more code")
        self.assertEqual(self.next()["action"], "review")

    def test_rework_then_escalate(self):
        self.started()
        for k in (1, 2, 3):
            self.write("src/cart.py", "x = %d\n" % k)
            self.commit("code %d" % k)
            self.review("01-cart-%d" % k, "REWORK")
            d = self.next()
            if k < 3:
                self.assertEqual((d["action"], d["k"]), ("rework", k))
                self.assertTrue(self.mm("next")[1].startswith("rework 01-cart %d — " % k))
            else:
                self.assertEqual((d["action"], d["k"]), ("escalate", 3))

    def test_release_review_confirm(self):
        self.done_release()
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("release-review", "R0"))
        self.review("R0-1", "HEALTHY")
        self.assertEqual(self.next()["action"], "confirm")

    def test_one_design_pass_then_confirm(self):
        self.done_release()
        self.review("R0-1", "DESIGN-PASS")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("design-pass", "R0"))
        self.commit("pass 1")
        self.review("R0-2", "DESIGN-PASS")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("confirm", "R0"))
        self.assertIn("after 1 design pass:", d["reason"])
        self.assertIn("--why", d["reason"])

    def test_a_release_without_smoke_asks_for_the_skeleton_before_its_review(self):
        self.done_release()
        self.write("CLAUDE.md", CLAUDE.replace("- smoke: true\n", ""))
        self.commit("no smoke")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("skeleton", "R0"))
        self.assertIn("release R0: no smoke: in CLAUDE.md ## mismagent", d["reason"])
        self.assertIn("R0: no smoke:", self.mm("tag", "R0")[2])

    def test_an_open_question_holds_the_release_review(self):
        self.done_release()
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\n- hide the POIs?\n")
        self.commit("design pass")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("idle", "R0"))
        self.assertIn("1 open question(s) in .mismagent/releases/R0.md: /mismagent:specify R0", d["reason"])
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\nnone\n")
        self.commit("specify R0: answered")
        self.assertEqual(self.next()["action"], "release-review")

    def test_a_none_line_with_a_comment_is_none(self):
        self.done_release()
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\nNone. Answered 2026-10-29: \"ok\" to "
                   "Q1-Q6, and to\nexamples EX-1..2 and slices 1-2.\n")
        self.commit("specify R0")
        self.assertEqual(self.next()["action"], "release-review")
        self.assertEqual(self.mm("check", "--release", "R0")[0], 0, self.mm("check", "--release", "R0")[1])
        self.write(".mismagent/releases/R0.md", self.read(".mismagent/releases/R0.md") + "- What about refunds?\n")
        self.commit("design pass")  # a question appended after the none paragraph still asks
        d = self.next()
        self.assertEqual(d["action"], "idle")
        self.assertIn("1 open question(s)", d["reason"])

    def test_a_question_in_a_later_release_does_not_hold_this_one(self):
        self.done_release()
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\nnone\n")
        self.write(".mismagent/releases/R1.md", "# R1\n\n## Open questions\n- the POIs, from R0's review\n")
        self.commit("specify R0")
        self.assertEqual(self.next()["action"], "release-review")

    def test_start_is_not_held_by_open_questions(self):
        self.slice("01-cart")
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\n- hide the POIs?\n")
        self.commit("plan")
        self.assertEqual(self.next()["action"], "start")

    def test_tagged_release_skipped(self):
        self.done_release()
        self.git("tag", "-a", "R0", "-m", "R0")
        d = self.next()
        self.assertEqual(d["action"], "idle")

    def test_design_pass_notes(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(6)))
        self.slice("01-cart")
        self.commit()
        d = self.next()
        self.assertEqual((d["action"], d.get("notes"), d["release"]), ("design-pass", 6, "R0"))
        self.assertTrue(self.mm("next")[1].startswith("design-pass notes — "))
        self.slice("05-cleanup", kind="refactor", examples="")
        self.commit()
        self.assertEqual(self.next(), {"action": "start", "slice": "05-cleanup",
                                       "path": ".mismagent/slices/todo/05-cleanup.md",
                                       "reason": "refactor slice first in todo"})

    def test_a_design_pass_that_leaves_the_backlog_idles_instead_of_looping(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(6)))
        self.slice("01-cart")
        self.commit("design pass")  # the architect read them and left them
        d = self.next()
        self.assertEqual((d["action"], d["notes"], d["release"]), ("idle", 6, "R0"))
        self.assertIn("6 design notes after the design pass (limit 5): the human decides", d["reason"])
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(7)))
        self.commit("mm land 02-pay")  # a new note: one more pass, for it
        self.assertEqual(self.next()["action"], "design-pass")

    def test_designed_records_a_pass_that_changed_nothing(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(6)))
        self.slice("01-cart")
        self.write("src/cart.py", "x = 1\n")
        before = self.commit()
        self.assertEqual(self.next()["action"], "design-pass")
        self.write("src/cart.py", "x = 2\n")  # a builder's work beside the pass: unstaged, staged, untracked
        self.write("src/more.py", "y = 1\n")
        self.git("add", "src/more.py")
        self.write("src/new.py", "z = 1\n")
        self.write(".mismagent/decisions/0001-human.md", "# specify's, half written\n")
        self.slice("08-draft", release="R1", examples="EX-3")  # and a slice specify has not agreed with the human
        status, index = self.git("status", "--porcelain", "--untracked-files=all"), self.git("ls-files", "-s")
        code, out, err = self.mm("designed", "R0: nothing to pay down")  # the architect read them and left them
        self.assertEqual(code, 0, err)
        self.assertIn("nothing changed", out)
        self.assertIn("left as they are, not named: .mismagent/decisions/0001-human.md, "
                      ".mismagent/slices/todo/08-draft.md", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "design pass R0: nothing to pay down")
        self.assertEqual((self.git("rev-parse", "HEAD~1"), self.git("rev-parse", "HEAD^{tree}")),
                         (before, self.git("rev-parse", before + "^{tree}")))  # an empty commit: the record `next` reads
        self.assertEqual((self.git("status", "--porcelain", "--untracked-files=all"), self.git("ls-files", "-s")),
                         (status, index))  # nobody's file taken, nothing staged or unstaged
        self.git("reset", "-q")
        self.git("clean", "-qfd")
        self.git("checkout", "-q", "--", ".")
        d = self.next()
        self.assertEqual((d["action"], d["notes"]), ("idle", 6))  # not design-pass again, on every call
        self.assertEqual(self.mm("designed", " ")[0], 1)  # a note of nothing

    def test_designed_commits_what_the_pass_wrote_and_nothing_else(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(7)))
        self.slice("01-cart")
        self.commit()
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(6)))
        self.write("ARCHITECTURE.md", "# Architecture\n\nOne module.\n")
        self.write(".mismagent/decisions/0001-seam.md", "# seam\n\n## Evidence\n- the code\n")
        self.write(".mismagent/slices/todo/05-cleanup.md", "# Slice\n\nKind: cleanup\nRelease: R0\n")
        self.write("src/cart.py", "x = 1\n")  # a builder's file, not the pass's
        self.write(".mismagent/decisions/0002-human.md", "# specify's, half written\n")  # nor is specify's, beside
        self.write(".mismagent/slices/todo/08-draft.md", "# Slice\n\nKind: nonsense\n")  # not agreed, not even whole
        wrote = ("ARCHITECTURE.md", ".mismagent/decisions/0001-seam.md", ".mismagent/slices/todo/05-cleanup.md")
        head = self.head()
        code, _, err = self.mm("designed", "R0: one refactor slice", *wrote)
        self.assertEqual(code, 1)  # the slice it wrote is malformed: the next gate would be red on it
        self.assertIn("what the design pass wrote does not hold together", err)
        self.assertIn("05-cleanup.md: Kind 'cleanup'", err)
        self.assertNotIn("08-draft", err)  # another session's file holds nothing: it is not in this commit
        self.assertEqual(self.head(), head)
        self.slice("05-cleanup", kind="refactor", examples="")
        self.write(".mismagent/slices/todo/05-cleanup.md",
                   self.read(".mismagent/slices/todo/05-cleanup.md").replace("Examples:", "After: 01\nExamples:"))
        for bad, why in ((".mismagent/decisions", "is a folder: name the files you wrote or deleted in it"),
                         (".mismagent/slices/todo/", "is a folder"), ("src/cart.py", "not a file `mm designed` commits"),
                         (".mismagent/examples/cart.md", "not a file `mm designed` commits")):
            code, _, err = self.mm("designed", "R0: one refactor slice", *wrote, bad)
            self.assertEqual((code, self.head()), (1, head), bad)
            self.assertIn(why, err)
        code, out, err = self.mm("designed", "R0: one refactor slice", *wrote, cwd=os.path.join(self.dir, "src"))
        self.assertEqual(code, 1)  # a name is read from where the caller stands
        code, out, err = self.mm("designed", "R0: one refactor slice", *("../" + w for w in wrote),
                                 cwd=os.path.join(self.dir, "src"))
        self.assertEqual(code, 0, err)
        self.assertIn("design pass R0: one refactor slice: 4 file(s)", out)
        self.assertIn("left as they are, not named: .mismagent/decisions/0002-human.md, "
                      ".mismagent/slices/todo/08-draft.md — another session's", out)
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split()),
                         [".mismagent/decisions/0001-seam.md", ".mismagent/design-notes.md",
                          ".mismagent/slices/todo/05-cleanup.md", "ARCHITECTURE.md"])
        self.assertEqual(sorted(self.git("status", "--porcelain", "--untracked-files=all").splitlines()),
                         ["?? .mismagent/decisions/0002-human.md", "?? .mismagent/slices/todo/08-draft.md",
                          "?? src/cart.py"])  # specify's and the builder's, as they were
        os.remove(os.path.join(self.dir, ".mismagent/decisions/0002-human.md"))
        os.remove(os.path.join(self.dir, ".mismagent/slices/todo/08-draft.md"))
        self.assertEqual(self.next()["action"], "idle")  # six notes left, the refactor slice waits: the human decides

    def test_a_design_pass_committed_by_hand_is_read_in_either_case(self):
        self.slice("01-cart")
        for n, subject in enumerate(("Design pass: R0 notes read, none paid down", "design-pass R0", "DESIGN PASS R0"), 6):
            self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(n)))
            self.commit("mm land 0%d-pay" % n)  # a new note: one more pass, for it
            self.assertEqual(self.next()["action"], "design-pass", subject)
            self.commit(subject)
            self.assertEqual(self.next()["action"], "idle", subject)  # not design-pass on every call

    def test_a_waiting_refactor_slice_does_not_hold_the_design_pass(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(6)))
        self.slice("01-cart")
        self.slice("24-ship", kind="refactor", examples="")
        rel = ".mismagent/slices/todo/24-ship.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 01\nExamples:"))
        self.commit()
        self.assertEqual(self.next()["action"], "design-pass")

    def test_five_notes_do_not_trigger(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(5)))
        self.slice("01-cart")
        self.commit()  # a slice still being written is specify's: `wait`
        self.assertEqual(self.next()["action"], "start")

    def test_start_order(self):
        self.slice("03-b")
        self.slice("02-a")
        self.commit()
        self.assertEqual(self.next()["slice"], "02-a")
        self.slice("07-r", kind="refactor", examples="")
        self.commit()
        self.assertEqual(self.next()["slice"], "07-r")

    def test_a_fix_starts_first(self):
        self.slice("02-a")
        self.slice("07-r", kind="refactor", examples="")
        self.slice("09-bug", kind="fix", examples="EX-2")
        self.commit()
        self.assertEqual(self.next()["slice"], "09-bug")

    def test_an_example_in_no_slice_holds_the_release(self):
        self.done_release()
        self.write(".mismagent/examples/pay.md", "| id | given | when | then | rule | req | release |\n"
                   "| EX-4 | a cart | pay | paid | R | Q3 | R0 |\n")
        self.commit()
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("idle", "R0"))
        self.assertIn("EX-4 in no slice", d["reason"])

    def test_skeleton_first(self):
        os.remove(os.path.join(self.dir, "ARCHITECTURE.md"))
        self.started()
        d = self.next()
        self.assertEqual(d["action"], "skeleton")
        self.assertIn("ARCHITECTURE.md", d["reason"])
        self.write("ARCHITECTURE.md", "# A\n")
        self.write("CLAUDE.md", "## mismagent\n- test: true\n")
        d = self.next()
        self.assertEqual(d["action"], "skeleton")
        self.assertIn("lint", d["reason"])

    def test_proposals_ride_on_start(self):
        self.done_release()
        self.slice("02-more", examples="EX-2")
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n\n- create errors: typed errors (`src/cart.py`)\n")
        self.commit()
        d = self.next()
        self.assertEqual((d["action"], d["slice"], d["proposals"]), ("start", "02-more", 1))
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n")
        self.commit()
        self.assertNotIn("proposals", self.next())

    def test_a_now_proposal_is_decided_before_the_next_slice(self):
        self.done_release()
        self.slice("02-more", examples="EX-2")
        self.write(".mismagent/conventions-proposals.md",
                   "- create errors: typed errors\n- now update db: no citation until `src/db.rs` lands\n")
        self.commit()
        d = self.next()
        self.assertEqual((d["action"], d["proposals"]), ("conventions", 2))

    def test_proposals_decided_before_the_release_review(self):
        self.done_release()
        self.write(".mismagent/conventions-proposals.md", "- create errors: typed errors\n")
        self.commit()
        d = self.next()
        self.assertEqual((d["action"], d["proposals"]), ("conventions", 1))
        self.write(".mismagent/conventions-proposals.md", "")
        self.commit()
        self.assertEqual(self.next()["action"], "release-review")

    def test_proposals_decided_when_no_slice_can_start(self):
        self.slice("02-more", examples="EX-2", release="R1")
        rel = ".mismagent/slices/todo/02-more.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 09\nExamples:"))
        self.commit()
        self.assertEqual(self.next()["action"], "idle")
        self.write(".mismagent/conventions-proposals.md", "- create errors: typed errors\n")
        self.commit()
        self.assertEqual(self.next()["action"], "conventions")

    def test_proposals_wait_for_the_doing_slice(self):
        self.started()
        self.write(".mismagent/conventions-proposals.md", "- create errors: typed errors\n")
        self.commit()
        self.assertEqual(self.next()["action"], "build")

    def test_conventions_after_the_model_slice_without_skill(self):
        os.remove(os.path.join(self.dir, ".claude/skills/conventions/SKILL.md"))
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(kind="model", examples="EX-1").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "def test_ex1():  # EX-1\n    pass\n")
        self.slice("02-more", examples="EX-2")
        self.commit()
        d = self.next()
        self.assertEqual(d["action"], "catalog")
        self.assertIn("no conventions skill and no proposal", d["reason"])
        self.write(".mismagent/conventions-proposals.md", "- create errors: Where src/ · Must typed\n")
        self.commit()
        d = self.next()
        self.assertEqual(d["action"], "conventions")
        self.assertIn("no conventions skill", d["reason"])

    def test_catalog_before_a_slice_in_doing(self):
        self.write(".claude/skills/conventions/references/tabs.md", "# tabs\n\nA feature rule.\n")
        self.slice("01-cart", state="doing", examples="EX-1", extra="Base: abc1234\n")
        self.commit()
        d = self.next()
        self.assertEqual(d["action"], "catalog")
        self.assertIn("1 convention topic(s) are not a kind of code or a practice (tabs.md)", d["reason"])
        self.write(".mismagent/conventions-proposals.md", "- now create swift-tab-model: Where Sources/ · Must x\n")
        self.commit()
        self.assertEqual(self.next()["action"], "conventions")

    def test_catalog_lists_every_malformed_topic_path(self):
        self.write(".claude/skills/conventions/references/tabs.md", "# tabs\n\nA feature rule.\n")
        self.write(".claude/skills/conventions/references/practices/pairing.md", "# pairing\n\n## Must\n- x\n")
        self.write(".claude/skills/conventions/references/message.md", "# message\n\n## Where\nx\n## Uses\nx\n"
                   "## Shape\nx\n## Must\n- x\n## Never\n- y\n## Example\n`CLAUDE.md`\n")
        self.slice("01-cart")
        self.commit()
        d = self.next()
        self.assertEqual(d["action"], "catalog")
        self.assertEqual(sorted(d["topics"]), [".claude/skills/conventions/references/practices/pairing.md",
                                               ".claude/skills/conventions/references/tabs.md"])
        self.assertIn("the others stay", d["reason"])

    def test_second_question_blocks_again(self):
        path = ".mismagent/slices/doing/01-cart.md"
        self.started(extra="\n## Question\nWhich currency?\n\n## Answer\nEUR.\n")
        self.assertEqual(self.next()["action"], "build")
        self.write(path, self.read(path) + "\n## Question\nRounding?\n")
        self.commit("q2")
        d = self.next()
        self.assertEqual((d["action"], d["path"]), ("blocked", path))
        self.write(path, self.read(path) + "\n## Question\n\n")  # an empty question does not block
        self.commit("q3")
        self.assertEqual(self.next()["action"], "build")

    def test_two_doing_slices_are_refused_with_the_way_out(self):
        self.slice("01-cart", state="doing", examples="EX-1", extra="Base: abc1234\n")
        self.slice("02-pay", state="doing", examples="EX-2", extra="Base: abc1234\n")
        self.commit("two checkouts met")
        d = self.next()
        self.assertEqual(d["action"], "stuck")
        self.assertIn("two slices in doing: 01-cart, 02-pay — one checkout holds one slice", d["reason"])
        self.assertIn("two slices in doing", self.mm("built", "01-cart", "--friction", "none")[2])
        self.assertIn("two slices in doing", self.mm("land", "01-cart")[2])

    def test_debris_is_not_dirty(self):
        self.started()
        for rel in ("src/__pycache__/a.cpython-312.pyc", ".pytest_cache/v/x", "app.db", "data.sqlite3",
                    "run.log", "b.pyc"):
            self.write(rel, "x")
        self.assertEqual(self.next()["action"], "build")
        self.write("notes.txt", "x")
        self.assertEqual(self.next()["action"], "resume")

    def test_json_paths(self):
        self.started()
        self.work()
        self.review("01-cart-1", "PASS")
        d = self.next()
        self.assertEqual((d["action"], d["path"], d["review"]),
                         ("land", ".mismagent/slices/doing/01-cart.md", ".mismagent/reviews/01-cart-1.md"))

    def test_an_old_scores_line_is_ignored(self):
        self.started()
        sha = self.work()
        self.write(".mismagent/reviews/01-cart-1.md", "VERDICT: PASS\nSHA: %s\nSCORES: naming=3\n" % sha[:9])
        self.assertEqual(self.next()["action"], "land")

    def test_a_risk_holds_the_release_review(self):
        self.done_release()
        self.review("R0-1", "HEALTHY")
        self.write(".mismagent/design-notes.md", "- src/x.py: long\n- RISK: src/cart.py:3: a negative total is accepted\n")
        self.commit("mm land 02-pay")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("design-pass", "R0"))
        self.assertIn("1 RISK note(s)", d["reason"])
        self.commit("design pass")  # the architect left the risk where it was
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("idle", "R0"))
        self.assertIn("the human decides", d["reason"])
        self.write(".mismagent/design-notes.md", "- src/x.py: long\n")
        self.commit("design pass")
        self.review("R0-2", "HEALTHY")
        self.assertEqual(self.next()["action"], "confirm")

    def test_a_risk_noted_after_a_design_pass_asks_for_another(self):
        self.done_release()
        self.write(".mismagent/design-notes.md", "- note\n")
        self.commit("design pass")
        self.write(".mismagent/design-notes.md", "- note\n- RISK (slice 52): a total is wrong\n")
        self.commit("mm land 03-more")
        self.assertEqual(self.next()["action"], "design-pass")

    def test_direct_then_stuck(self):
        self.started()
        for k in (1, 2, 3):
            self.work(code="x = %d\n" % k)
            self.review("01-cart-%d" % k, "REWORK")
        self.assertEqual(self.next()["action"], "escalate")
        self.review("01-cart-4", "DIRECT")
        d = self.next()
        self.assertEqual((d["action"], d["review"]), ("rework", ".mismagent/reviews/01-cart-4.md"))
        self.assertIn("DIRECT", d["reason"])
        self.work(code="x = 9\n")
        self.assertEqual(self.next()["action"], "review")
        self.review("01-cart-5", "REWORK")
        d = self.next()
        self.assertEqual(d["action"], "stuck")
        self.assertIn("01-cart-4.md", d["reason"])
        self.review("01-cart-5", "PASS")
        self.assertEqual(self.next()["action"], "land")

    def test_architect_pass_after_escalate_lands(self):
        self.started()
        for k in (1, 2, 3):
            self.work(code="x = %d\n" % k)
            self.review("01-cart-%d" % k, "REWORK")
        self.review("01-cart-4", "PASS")
        self.assertEqual(self.next()["action"], "land")

    def test_idle(self):
        d = self.next()
        self.assertEqual(d["action"], "idle")
        self.assertIn("specify", d["reason"])


class StartLand(Repo):
    def test_start_moves_writes_base_commits(self):
        self.slice("01-cart")
        before = self.commit("plan")
        code, out, err = self.mm("start", "01")
        self.assertEqual(code, 0, err)
        self.assertIn(".mismagent/slices/doing/01-cart.md", out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/slices/todo/01-cart.md")))
        text = self.read(".mismagent/slices/doing/01-cart.md")
        self.assertIn("Base: " + before, text)
        self.assertLess(text.index("Examples:"), text.index("Base:"))
        self.assertEqual(self.git("log", "-1", "--format=%s"), "mm start 01-cart")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_start_preconditions(self):
        self.slice("01-cart")
        self.slice("02-more")
        self.commit("plan")
        self.write("src/x.py", "x = 1\n")
        code, _, err = self.mm("start", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("dirty", err)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.commit()
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        code, _, err = self.mm("start", "02-more")
        self.assertEqual(code, 1)
        self.assertIn("already in doing", err)
        self.assertEqual(self.mm("start", "01-cart")[0], 1)  # not in todo
        self.assertEqual(self.mm("start", "99-none")[0], 1)

    def test_land_refuses_an_example_without_marker(self):
        self.started()
        self.git("rm", "-q", "tests/acceptance/test_01-cart.py")
        self.write("src/cart.py", "x = 1\n")
        self.commit("01-cart: code, the marker file lost")  # without mm built, which would refuse first
        self.review("01-cart-1", "PASS")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("EX-1 has no acceptance marker under tests/acceptance/", err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/01-cart.md")))

    def body(self, text="| dimension | checked |\n\nNo blocking finding.\n"):
        self.write(".mismagent/reviews/01-cart.draft.md", text)
        return os.path.join(self.dir, ".mismagent/reviews/01-cart.draft.md")

    def test_review_writes_the_header(self):
        self.started()
        sha = self.work()
        self.body()
        code, out, err = self.mm("review", "01-cart", "pass", "--sha", sha[:9])
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), ".mismagent/reviews/01-cart-1.md")
        text = self.read(".mismagent/reviews/01-cart-1.md")
        self.assertTrue(text.startswith("VERDICT: PASS\nSHA: %s\n\n" % sha), text)
        self.assertIn("No blocking finding.", text)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/01-cart.draft.md")))
        self.assertEqual(self.next()["action"], "land")

    def test_review_refusals(self):
        self.started()
        sha = self.work()
        def review(*args):
            return self.mm("review", *args, "--body", self.body())
        self.assertIn("HEAD moved", review("01-cart", "PASS", "--sha", "abcdef1")[2])
        self.assertIn("takes PASS | REWORK | DIRECT", review("01-cart", "HEALTHY", "--sha", sha)[2])
        self.assertIn("missing or empty", self.mm("review", "01-cart", "REWORK", "--sha", sha,
                                                  "--body", "nope.md")[2])
        self.assertEqual(review("01-cart", "DIRECT", "--sha", sha)[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/01-cart-2.md")))
        self.assertIn("neither a slice nor a release", review("R9", "HEALTHY", "--sha", sha)[2])
        self.assertIn("R0: not ready for a release review: slices not done: 01-cart",
                      review("R0", "DESIGN-PASS", "--sha", sha)[2])

    def test_a_release_review_may_record_the_risk_it_found(self):
        self.done_release()
        self.write(".mismagent/design-notes.md", "- RISK: src/cart.py:3: a negative total is accepted\n")
        self.write(".mismagent/reviews/R0.draft.md", "errors: a wrong result, noted as a risk\n")
        code, _, err = self.mm("review", "R0", "DESIGN-PASS", "--sha", self.head())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.next()["action"], "design-pass")  # the risk, then the pass the review asks for

    def test_a_release_review_needs_every_slice_done(self):
        self.started()
        sha = self.work()
        code, _, err = self.mm("review", "R0", "HEALTHY", "--sha", sha, "--body", self.body())
        self.assertEqual(code, 1)
        self.assertIn("R0: not ready for a release review: slices not done: 01-cart", err)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/R0-1.md")))

    def test_an_uncommitted_proposal_does_not_dirty_the_tree_for_review(self):
        self.started()
        sha = self.work()
        self.write(".mismagent/conventions-proposals.md", "- create message: Where src/ · Shape … — src/cart.py\n")
        code, out, err = self.mm("review", "01-cart", "PASS", "--sha", sha, "--body", self.body())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.next()["action"], "land")

    def test_land_commits_proposals_with_reviews_and_notes(self):
        self.started()
        sha = self.work()
        self.write(".mismagent/conventions-proposals.md", "- create message: Where src/ · Shape … — src/cart.py\n")
        self.write(".mismagent/design-notes.md", "- src/x.py: long\n")
        self.review("01-cart-1", "PASS")
        self.assertEqual(self.mm("land", "01-cart")[0], 0)
        self.assertEqual(self.git("status", "--porcelain"), "")
        shown = self.git("show", "--name-only", "--format=", "HEAD")
        self.assertIn(".mismagent/conventions-proposals.md", shown)
        self.assertIn(".mismagent/design-notes.md", shown)

    def test_land_never_commits_a_draft(self):
        self.started()
        self.acceptance("test_cart.py", "# EX-1\n")
        sha = self.work()
        self.review("01-cart-1", "PASS", sha=sha)
        self.write(".mismagent/reviews/01-cart.draft.md", "left by a refused attempt\n")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/01-cart.draft.md")))
        self.assertNotIn("draft", self.git("show", "--name-only", "--format=", "HEAD"))

    def test_review_refuses_a_draft_older_than_head(self):
        self.started()
        sha = self.work()
        draft = self.body()
        old = int(self.git("log", "-1", "--format=%ct")) - 60
        os.utime(draft, (old, old))
        code, _, err = self.mm("review", "01-cart", "DIRECT", "--sha", sha)
        self.assertEqual(code, 1)
        self.assertIn("01-cart.draft.md was written before HEAD", err)

    def test_headers_never_overwrite_prose(self):
        self.write(".mismagent/slices/todo/01-cart.md", "# Slice\n\nKind: feature\nRelease: R0\nExamples: EX-1\n"
                   "Built on the cart model.\nAfter a tap the cart shows one item.\n\n## Goal\nDo it.\n")
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("plan")
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.work()
        text = self.read(".mismagent/slices/doing/01-cart.md")
        self.assertIn("Built on the cart model.\nAfter a tap the cart shows one item.", text)
        self.assertIn("Examples: EX-1\nBase: ", text)
        self.assertIn("\nBuilt: 1\n", text)

    def test_land_preconditions_and_commit(self):
        self.started()
        self.acceptance("test_cart.py", "def test_ex1():  # EX-1\n    pass\n")
        self.commit("code")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("no PASS", err)
        self.review("01-cart-1", "REWORK")
        self.assertEqual(self.mm("land", "01-cart")[0], 1)
        self.review("01-cart-2", "PASS")
        self.write("src/extra.py", "y = 2\n")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual((code, "dirty" in err), (1, True))
        os.remove(os.path.join(self.dir, "src/extra.py"))
        self.write("CLAUDE.md", CLAUDE.replace("`true`", "false"))
        self.git("commit", "-qam", "red lint")
        self.review("01-cart-2", "PASS")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("gate red: lint", err)
        self.write("CLAUDE.md", CLAUDE.replace("`true`", "echo lint-says-E999 && false"))
        self.git("commit", "-qam", "red lint with output")
        self.review("01-cart-2", "PASS")
        code, _, err = self.mm("land", "01-cart")
        self.assertIn("lint-says-E999", err)
        self.write("CLAUDE.md", CLAUDE)
        self.git("commit", "-qam", "green lint")
        self.review("01-cart-3", "PASS")
        code, out, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/done/01-cart.md")))
        self.assertEqual(self.git("log", "-1", "--format=%s"), "mm land 01-cart")
        self.assertIn(".mismagent/reviews/01-cart-3.md", self.git("show", "--name-only", "--format="))
        self.assertEqual(self.git("status", "--porcelain"), "")


    def test_park_returns_a_slice_without_work_to_todo(self):
        self.started()
        self.write(".mismagent/slices/doing/01-cart.md",
                   self.read(".mismagent/slices/doing/01-cart.md") + "\n## Question\nStack?\n## Answer\nSee 0002.\n")
        self.commit("answer")
        code, out, err = self.mm("park", "01-cart")
        self.assertEqual(code, 0, err)
        text = self.read(".mismagent/slices/todo/01-cart.md")
        self.assertNotIn("Base:", text)
        self.assertIn("## Answer", text)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "mm park 01-cart")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.next()["action"], "start")

    def test_park_preconditions(self):
        self.slice("01-cart")
        self.commit("plan")
        self.assertEqual(self.mm("park", "01-cart")[0], 1)  # not in doing
        self.mm("start", "01-cart")
        self.write("src/cart.py", "x = 1\n")
        code, _, err = self.mm("park", "01-cart")
        self.assertEqual((code, "dirty" in err), (1, True))
        self.commit("code")
        code, _, err = self.mm("park", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("work since Base", err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/01-cart.md")))

    def test_park_refuses_a_missing_or_invalid_base(self):
        self.started()
        rel = ".mismagent/slices/doing/01-cart.md"
        original = self.read(rel)
        for base in ("", "Base: 0000000000000000000000000000000000000000\n"):
            text = re.sub(r"Base: .*\n", base, original)
            self.assertEqual(bool(base), "Base:" in text)
            self.write(rel, text)
            self.commit("base " + (base or "missing"))
            code, _, err = self.mm("park", "01-cart")
            self.assertEqual(code, 1)
            self.assertIn("no valid Base", err)
            self.assertTrue(os.path.exists(os.path.join(self.dir, rel)))

    def test_a_parked_slice_waits_for_its_after_slices(self):
        self.started("01-work", kind="refactor", examples="")
        self.mm("park", "01-work")
        self.slice("02-migrate", kind="refactor", examples="")
        self.slice("03-migrate-more", kind="refactor", examples="")
        rel = ".mismagent/slices/todo/01-work.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 02, 03-migrate-more\nExamples:"))
        self.commit("migration queued")
        self.assertEqual(self.check()[0], 0, self.check()[2])
        self.assertEqual(self.next()["slice"], "02-migrate")
        os.makedirs(os.path.join(self.dir, ".mismagent/slices/done"), exist_ok=True)
        self.git("mv", ".mismagent/slices/todo/02-migrate.md", ".mismagent/slices/done/02-migrate.md")
        self.commit("02 done")
        self.assertEqual(self.next()["slice"], "03-migrate-more")  # 01 still waits for 03
        self.git("mv", ".mismagent/slices/todo/03-migrate-more.md", ".mismagent/slices/done/03-migrate-more.md")
        self.commit("03 done")
        self.assertEqual(self.next()["slice"], "01-work")

    def test_every_todo_slice_waiting_is_idle(self):
        self.slice("01-a", extra="")
        rel = ".mismagent/slices/todo/01-a.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 02\nExamples:"))
        self.slice("02-b", state="doing")
        self.write(".mismagent/slices/doing/02-b.md",
                   self.read(".mismagent/slices/doing/02-b.md").replace("Examples:", "Base: %s\nExamples:" % self.head()))
        self.commit("plan")
        self.git("mv", ".mismagent/slices/doing/02-b.md", ".mismagent/slices/todo/02-b.md")
        self.write(".mismagent/slices/todo/02-b.md",
                   self.read(".mismagent/slices/todo/02-b.md").replace("Examples:", "After: 01\nExamples:"))
        self.commit("a cycle")
        d = self.next()
        self.assertEqual(d["action"], "idle")
        self.assertIn("waits", d["reason"])

    def test_check_refuses_an_after_naming_no_slice(self):
        self.slice("01-a")
        rel = ".mismagent/slices/todo/01-a.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 07, 01-a\nExamples:"))
        self.commit("plan")
        code, out, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("After: '07'", out + err)
        self.assertIn("After: '01-a'", out + err)

    def test_an_open_stack_review_holds_the_flow(self):
        self.started()
        status = ".mismagent/stack-reviews/0002-status.md"
        self.write(status, "entry: standalone\nslice: 01-cart\nstep: 6\nnext: handoff\nstate: decided\n")
        self.commit("stack 0002 decided")
        d = self.next()
        self.assertEqual(d["action"], "idle")
        self.assertIn("0002", d["reason"])
        self.write(status, "entry: standalone\nstep: 7\nnext: none\n- **State:** done\n")
        self.commit("stack 0002 done")
        self.assertEqual(self.next()["action"], "build")
        self.write(status, "entry: standalone\n")  # no state: open until it says done
        self.commit("status rewritten")
        self.assertEqual(self.next()["action"], "idle")

    def test_start_refuses_a_held_flow_or_a_waiting_slice(self):
        self.slice("01-a")
        self.slice("02-b")
        rel = ".mismagent/slices/todo/02-b.md"
        self.write(rel, self.read(rel).replace("Examples:", "After: 01\nExamples:"))
        self.write(".mismagent/stack-reviews/0002-status.md", "state: open\n")
        before = self.commit("plan")
        code, _, err = self.mm("start", "01-a")
        self.assertEqual((code, "stack review 0002 is open" in err), (1, True))
        self.write(".mismagent/stack-reviews/0002-status.md", "state: done\n")
        before = self.commit("review done")
        code, _, err = self.mm("start", "02-b")
        self.assertEqual((code, "waits for 01" in err), (1, True))
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (before, ""))
        self.assertTrue(os.path.exists(os.path.join(self.dir, rel)))
        self.assertEqual(self.mm("start", "01-a")[0], 0)

class Gate(Repo):
    def test_gate_green(self):
        code, out, _ = self.mm("gate")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"test: green \(true\) \d+ s")
        self.assertRegex(out, r"gate: green \(\d+ s\)")

    def test_a_command_green_on_this_code_tree_is_not_run_again(self):
        runs = self.counting()
        code, out, _ = self.mm("gate")
        self.assertEqual((code, runs()), (0, 1))
        log = re.search(r"test: green .* · output: (\S+)", out).group(1)
        said, _, body = self.read(log).partition("\n")  # which run it is, then all of its output
        line, _, when = said.rpartition(", ")
        self.assertEqual(line, "# " + re.search(r"^(test: green \(.*\) \d+ s) · output", out, re.M).group(1))
        self.assertIn("test: green (echo run >> .git/runs; seq 1 40; echo test_cart PASSED) ", line)
        self.assertLess(abs(time.mktime(time.strptime(when, "%Y-%m-%d %H:%M:%S")) - time.time()), 120)
        self.assertEqual(body.split(), [str(i) for i in range(1, 41)] + ["test_cart", "PASSED"])
        code, out, _ = self.mm("gate")
        self.assertEqual((code, runs()), (0, 1))
        self.assertRegex(out, r"test: green \(.*\) \d+ s — run \S+ \S+ on this code tree, not run again .* output: " + re.escape(log))
        self.assertRegex(out, r"gate: green \(\d+ s\)")
        self.write(".mismagent/slices/todo/02-more.md", slice_text(examples="EX-2"))  # a card: no code
        self.commit("specify R0: slice 02")
        self.assertEqual((self.mm("gate")[0], runs()), (0, 1))
        self.write("src/cart.py", "x = 2\n")  # code: another tree
        self.commit("code")
        self.assertEqual((self.mm("gate")[0], runs()), (0, 2))

    def test_fresh_runs_what_is_on_record(self):
        runs = self.counting()
        self.mm("gate")
        code, out, _ = self.mm("gate", "--fresh")
        self.assertEqual((code, runs()), (0, 2))
        self.assertNotIn("not run again", out)

    def test_nothing_is_on_record_from_a_dirty_tree_a_red_run_or_a_command_that_changed_the_code(self):
        runs = self.counting()
        self.write("src/cart.py", "x = 1\n")  # uncommitted: the tree on disk is no commit's
        self.mm("gate")
        _, out, _ = self.mm("gate")
        self.assertEqual(runs(), 2)
        self.assertIn("test: not on record (uncommitted: src/cart.py)", out)
        self.commit("code")
        runs = self.counting(lint="false")  # red: lint, after a green test
        self.assertEqual(self.mm("gate")[0], 1)
        self.assertEqual(self.mm("gate")[0], 1)
        self.assertEqual(runs(), 3)  # the green test is on record, the red lint never: it ran twice, red twice
        self.write("CLAUDE.md", "## mismagent\n- test: echo run >> .git/runs; echo y >> src/cart.py\n- lint: true\n")
        self.commit("a test that writes the code")
        self.mm("gate")
        self.git("checkout", "--", "src/cart.py")
        code, out, _ = self.mm("gate")
        self.assertNotIn("not run again", out)
        self.assertIn("test: not on record (the command changed a tracked file on disk)", out)
        self.assertEqual(runs(), 5)

    def test_a_round_runs_the_suite_once_built_reviewed_and_landed(self):
        runs = self.counting()
        self.started()
        sha = self.work()  # mm built: the one run
        self.assertEqual(runs(), 1)
        code, out, _ = self.mm("gate", "--base", parse_base(self.read(".mismagent/slices/doing/01-cart.md")))
        self.assertEqual(code, 0, out)
        self.assertIn("not run again", out)  # the reviewer's gate: the base check, and the run named
        self.review("01-cart-1", "PASS", sha)
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        self.assertEqual(runs(), 1)

    def test_built_counts_the_seconds_of_a_run_it_did_not_repeat(self):
        self.write("CLAUDE.md", "## mismagent\n- test: sleep 1\n- lint: true\n")
        self.started()
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        self.assertEqual(self.mm("gate")[0], 0)  # the builder's own, on the committed tree
        code, _, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 0, err)
        self.assertRegex(self.read(".mismagent/slices/doing/01-cart.md"), r"Gate: 1: [1-9]")

    def test_the_record_keeps_the_newest_code_trees(self):
        self.counting()
        trees = []
        for i in range(7):
            self.write("src/cart.py", "x = %d\n" % i)
            self.commit("code %d" % i)
            self.assertEqual(self.mm("gate")[0], 0)
            time.sleep(0.02)
            trees.append(re.search(r"mismagent\.gate/(\w+)\.test\.", self.mm("gate")[1]).group(1))
        kept = os.listdir(os.path.join(self.dir, ".git", "mismagent.gate"))
        self.assertEqual({n.split(".")[0] for n in kept}, set(trees[-5:]))  # the newest five, whole
        self.assertEqual(len(kept), 5 * 4, kept)  # a record and its output, test and lint

    def test_a_red_fresh_run_is_never_followed_by_the_old_green(self):
        self.write("CLAUDE.md", "## mismagent\n- test: test ! -e .git/broken && echo run >> .git/runs\n- lint: true\n")
        self.commit("gate")
        self.assertEqual(self.mm("gate")[0], 0)
        self.write(".git/broken", "")  # what no commit holds went wrong
        self.assertEqual(self.mm("gate")[0], 0)  # on record: not seen
        green = re.search(r"test: green .* · output: (\S+)", self.mm("gate")[1]).group(1)
        self.assertTrue(self.read(green).startswith("# test: green (test ! -e .git/broken"))
        self.assertEqual(self.mm("gate", "--fresh")[0], 1)  # seen
        self.assertTrue(self.read(green).startswith("# test: red (test ! -e .git/broken"))  # the same file says which run
        self.assertFalse(os.path.exists(os.path.join(self.dir, green + ".tmp")))
        code, out, _ = self.mm("gate")
        self.assertEqual(code, 1, out)  # and not forgotten: land and tag would run it too
        os.remove(os.path.join(self.dir, ".git", "broken"))
        code, out, _ = self.mm("gate")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"test: green \(.*\) \d+ s · output")  # run now, not read from the record
        self.assertEqual(len(self.read(".git/runs").split()), 2)

    def test_two_names_a_carriage_return_apart_are_two_trees(self):
        runs = self.counting()
        self.write("input\rdata", "x\n")
        self.commit("cr")
        self.assertEqual((self.mm("gate")[0], runs()), (0, 1))
        self.git("mv", "input\rdata", "input\ndata")
        self.commit("lf")
        self.assertEqual((self.mm("gate")[0], runs()), (0, 2))

    def test_untracked_debris_and_a_submodule_keep_a_run_off_the_record(self):
        runs = self.counting()
        self.assertEqual(self.mm("gate")[0], 0)
        self.write("src/broken.sqlite.py", "def broken(\n")  # debris by its name, source by what it is
        code, out, _ = self.mm("gate")
        self.assertEqual((code, runs()), (0, 2))
        self.assertIn("test: not on record (uncommitted: src/broken.sqlite.py)", out)
        os.remove(os.path.join(self.dir, "src/broken.sqlite.py"))
        os.makedirs(os.path.join(self.dir, "vendor"))
        for args in (("init", "-q"), ("-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-q",
                                      "--allow-empty", "-m", "x")):
            subprocess.run(["git", *args], cwd=os.path.join(self.dir, "vendor"), check=True, capture_output=True)
        self.commit("a gitlink")
        self.mm("gate")
        code, out, _ = self.mm("gate")
        self.assertEqual((code, runs()), (0, 4))
        self.assertIn("test: not on record (a submodule's files are no part of this commit)", out)

    def test_one_gates_commands_at_a_time_and_the_second_finds_the_first_on_record(self):
        self.write("CLAUDE.md", "## mismagent\n- test: mkdir .git/busy && sleep 0.3 && rmdir .git/busy && echo run >> .git/runs\n"
                   "- lint: true\n")  # two at once: the second mkdir fails
        self.commit("gate")
        for args, runs in ((("gate", "--fresh"), 5), (("gate",), 6)):
            ps = [subprocess.Popen([sys.executable, MM, *args], cwd=self.dir, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True) for _ in range(5)]
            outs = [p.communicate() + (p.returncode,) for p in ps]
            self.assertEqual([code for _, _, code in outs], [0] * 5, outs)
            self.assertTrue(any("another gate is running in this checkout" in out for out, _, _ in outs))
            if runs == 5:
                self.forget_gate()  # then five plain gates at once: one runs, four read its record
            self.assertEqual(len(self.read(".git/runs").split()), runs)

    def test_a_file_moved_into_mismagent_is_gone_from_where_it_was(self):
        self.write("src/cart.py", "x = 1\n")
        self.write("CLAUDE.md", "## mismagent\n- test: test -f src/cart.py && echo run >> .git/runs\n- lint: true\n")
        self.commit("gate")
        self.assertEqual(self.mm("gate")[0], 0)
        os.makedirs(os.path.join(self.dir, ".mismagent/reviews"))
        self.git("mv", "src/cart.py", ".mismagent/reviews/cart.py")  # staged: a rename, its new name under .mismagent/
        code, out, _ = self.mm("gate")
        self.assertEqual(code, 1, out)
        self.assertNotIn("not run again", out)

    def test_the_command_after_one_that_changed_the_code_runs(self):
        self.write("src/cart.py", "x = 1\n")
        self.write("CLAUDE.md", "## mismagent\n- test: test -e .git/go && echo y >> src/cart.py\n"
                   "- lint: echo run >> .git/runs\n")
        self.commit("gate")
        self.assertEqual(self.mm("gate")[0], 1)  # test red, lint green: on record
        self.write(".git/go", "")
        code, out, _ = self.mm("gate")  # test green, and it wrote the code lint reads
        self.assertEqual(code, 0, out)
        self.assertIn("test: not on record (the command changed a tracked file on disk)", out)
        self.assertIn("lint: not on record (uncommitted: src/cart.py)", out)
        self.assertEqual(len(self.read(".git/runs").split()), 2)

    def test_a_record_that_is_not_one_or_has_lost_its_output_is_a_run(self):
        runs = self.counting()
        _, out, _ = self.mm("gate")
        log = re.search(r"test: green .* · output: (\S+)", out).group(1)
        record = log[:-len("log")] + "json"
        good = json.loads(self.read(record))
        for n, bad in enumerate(([good], {"cmd": good["cmd"], "at": good["at"]}, dict(good, seconds="3"),
                                 dict(good, at=[1]), dict(good, at=10 ** 30), "{",
                                 {k: v for k, v in good.items() if k != "disk"}, dict(good, disk="0" * 16)), 2):
            self.write(record, bad if isinstance(bad, str) else json.dumps(bad))
            code, out, err = self.mm("gate")
            self.assertEqual((code, runs()), (0, n), err)
        os.remove(os.path.join(self.dir, log))
        self.assertEqual((self.mm("gate")[0], runs()), (0, 10))
        self.assertEqual((self.mm("gate")[0], runs()), (0, 10))

    def disk_test(self, test):
        """A project whose suite reads what a tracked file is on disk; -> its gate: (exit code, ran or read)."""
        self.write("src/cart.py", "x = 1\n")
        self.write("src/total.py", "y = 1\n")
        self.write("CLAUDE.md", "## mismagent\n- test: %s\n- lint: true\n" % test)
        self.commit("gate")

        def gate():
            code, out, _ = self.mm("gate")
            self.assertEqual(self.git("status", "--porcelain"), "", "git sees nothing: the disk is mm's to look at")
            return code, "read" if re.search(r"^test: .* not run again", out, re.M) else "ran"
        return gate

    def test_a_file_a_sparse_checkout_took_away_or_git_was_told_to_assume_is_looked_at(self):
        gate = self.disk_test("test -f src/cart.py && grep -q 'y = 1' src/total.py")
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        self.git("sparse-checkout", "set", "--no-cone", "/*", "!/src/cart.py")  # gone from disk, and status is clean
        self.assertEqual(gate(), (1, "ran"))
        self.git("sparse-checkout", "disable")
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        self.git("update-index", "--assume-unchanged", "src/total.py")
        self.assertEqual(gate(), (0, "read"))  # told to assume, and unchanged: the same files
        self.write("src/total.py", "y = 2222\n")
        self.assertEqual(gate(), (1, "ran"))

    def test_a_mode_bit_git_ignores_is_looked_at(self):
        gate = self.disk_test("test -x src/cart.py")  # 100644 in the commit
        self.git("config", "core.filemode", "false")
        os.chmod(os.path.join(self.dir, "src/cart.py"), 0o755)
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))  # green on this disk, as a run would be
        os.chmod(os.path.join(self.dir, "src/cart.py"), 0o644)  # the commit's mode again: other files than the run read
        self.assertEqual(gate(), (1, "ran"))
        os.chmod(os.path.join(self.dir, "src/cart.py"), 0o755)
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.chmod(os.path.join(self.dir, "src/cart.py"), 0o654)  # the owner's bit alone gone
        self.assertEqual(gate(), (1, "ran"))

    def test_a_name_git_folds_is_looked_at_as_it_is_written(self):
        for committed, on_disk, why in (("CART.py", "cart.py", "case"), ("caf\u00e9.py", "cafe\u0301.py", "composition")):
            with self.subTest(why):
                gate = self.disk_test("ls src | grep -qx '%s'" % on_disk)
                self.write("src/" + committed, "x = 1\n")
                self.commit(why)
                here = lambda name: os.path.join(self.dir, "src", name)  # noqa: E731
                if not os.path.exists(here(on_disk)):
                    self.skipTest("this filesystem tells %r from %r: git sees the rename" % (committed, on_disk))
                os.rename(here(committed), here(on_disk))
                if on_disk not in os.listdir(os.path.join(self.dir, "src")) or self.git("status", "--porcelain"):
                    self.skipTest("the rename by %s is not kept by this filesystem, or git sees it" % why)
                self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))  # green on this disk
                os.rename(here(on_disk), here(committed))  # the commit's spelling: not what the run read
                self.assertEqual(gate(), (1, "ran"))

    def test_a_directory_respelt_or_closed_to_writing_and_a_link_added_or_retargeted_are_looked_at(self):
        gate = self.disk_test("true")
        os.symlink("total.py", os.path.join(self.dir, "src/link"))
        self.commit("a link")
        self.git("update-index", "--assume-unchanged", "src/link", "src/cart.py")
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.remove(os.path.join(self.dir, "src/link"))
        os.symlink("./total.py", os.path.join(self.dir, "src/link"))  # the same file by another link: lstat, not stat
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.chmod(os.path.join(self.dir, "src"), 0o555)  # a suite that writes beside its source now fails
        try:
            self.assertEqual(gate(), (0, "ran"))
        finally:
            os.chmod(os.path.join(self.dir, "src"), 0o755)
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.link(os.path.join(self.dir, "src/cart.py"), os.path.join(self.dir, ".mismagent/hard-link"))
        self.assertEqual(self.mm("gate")[1].count("not run again"), 0)  # one more name for the file (status: the card's folder)
        os.remove(os.path.join(self.dir, ".mismagent/hard-link"))
        self.mm("gate")
        at = os.stat(os.path.join(self.dir, "src/cart.py"))
        self.write("src/cart.py", "x = 123456\n")  # another size, the time of its last write set back
        os.utime(os.path.join(self.dir, "src/cart.py"), ns=(at.st_atime_ns, at.st_mtime_ns))
        self.assertEqual(self.mm("gate")[1].count("not run again"), 0)
        self.mm("gate")
        at = os.stat(os.path.join(self.dir, "src/cart.py"))
        os.utime(os.path.join(self.dir, "src/cart.py"), ns=(at.st_atime_ns, at.st_mtime_ns + 1000))  # a microsecond later
        self.assertEqual(self.mm("gate")[1].count("not run again"), 0)
        if os.path.exists(os.path.join(self.dir, "SRC")):  # a filesystem that folds case: git sees no rename
            os.rename(os.path.join(self.dir, "src"), os.path.join(self.dir, "SRC"))
            self.assertEqual(self.mm("gate")[1].count("not run again"), 0)

    def test_a_change_that_is_no_write_and_a_flag_on_a_directory_are_looked_at(self):
        gate = self.disk_test("true")
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        cart, src = os.path.join(self.dir, "src/cart.py"), os.path.join(self.dir, "src")
        before = os.lstat(cart)
        if hasattr(os, "chflags"):  # BSD, macOS: a flag — what an ACL or an extended attribute moves too: ctime alone
            import stat
            os.chflags(cart, stat.UF_NODUMP)
        elif hasattr(os, "setxattr"):
            try:
                os.setxattr(cart, "user.mm", b"1")
            except OSError:
                self.skipTest("no extended attributes on this filesystem")
        else:
            self.skipTest("no way here to change a file without writing it")
        after = os.lstat(cart)
        self.assertEqual((before.st_mode, before.st_size, before.st_nlink, before.st_mtime_ns),
                         (after.st_mode, after.st_size, after.st_nlink, after.st_mtime_ns))
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        if hasattr(os, "chflags"):
            os.chflags(src, stat.UF_NODUMP)  # as an immutable folder would be flagged: its mode the same
            self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))

    def test_a_tracked_file_touched_or_rewritten_by_a_checkout_is_a_run(self):
        gate = self.disk_test("true")
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.utime(os.path.join(self.dir, "src/cart.py"), (1, 1))  # the same bytes, written at another time
        self.assertEqual((gate(), gate()), ((0, "ran"), (0, "read")))
        os.remove(os.path.join(self.dir, "src/total.py"))
        self.git("checkout", "--", "src/total.py")  # as a checkout writes it: a filter's bytes, a new file
        self.assertEqual(gate(), (0, "ran"))
        self.write("CLAUDE.md", "## mismagent\n- test: touch src/cart.py\n- lint: true\n")
        self.commit("a suite that touches the code")
        self.mm("gate")
        code, out, _ = self.mm("gate")
        self.assertIn("test: not on record (the command changed a tracked file on disk)", out)

    def test_a_gate_does_not_wait_past_its_time_for_another(self):
        import fcntl
        self.assertEqual(self.mm("gate")[0], 0)  # the folder and the lock exist
        fd = os.open(os.path.join(self.dir, ".git", "mismagent.gate.lock"), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)  # a gate alive and stopped
        try:
            code, out, err = self.mm("gate", "--fresh", env=dict(os.environ, MM_GATE_WAIT="0.5"))
        finally:
            os.close(fd)
        self.assertEqual(code, 1)
        self.assertIn("another gate still runs in this checkout", err)
        self.assertEqual(self.mm("gate")[0], 0)

    def test_trees_wholly_red_leave_with_the_others(self):
        self.write("CLAUDE.md", "## mismagent\n- test: echo out; false\n- lint: false\n")
        trees = []
        for i in range(7):
            self.write("src/cart.py", "x = %d\n" % i)
            self.commit("code %d" % i)
            code, out, _ = self.mm("gate")
            self.assertEqual(code, 1)
            trees.append(re.search(r"mismagent\.gate/(\w+)\.test\.log", out).group(1))
            time.sleep(0.02)
        kept = os.listdir(os.path.join(self.dir, ".git", "mismagent.gate"))
        self.assertEqual(sorted(kept), sorted("%s.%s.log" % (t, k) for t in trees[-5:] for k in ("test", "lint")))

    def test_red_and_dirty_runs_leave_no_more_output_than_the_trees_kept(self):
        self.write("CLAUDE.md", "## mismagent\n- test: echo out; false\n- lint: true\n")
        for i in range(7):
            self.write("src/cart.py", "x = %d\n" % i)
            self.mm("gate")  # dirty
            self.commit("code %d" % i)
            self.assertEqual(self.mm("gate")[0], 1)  # red test, green lint
            time.sleep(0.02)
        kept = os.listdir(os.path.join(self.dir, ".git", "mismagent.gate"))
        self.assertEqual(len({n.split(".")[0] for n in kept} - {"uncommitted"}), 5)
        self.assertEqual(sorted(n for n in kept if n.startswith("uncommitted.")), ["uncommitted.lint.log", "uncommitted.test.log"])
        self.assertEqual(len(kept), 5 * 3 + 2, kept)  # a tree: the red test's output, lint's record and output

    def test_gate_red_test_or_lint(self):
        for key in ("test", "lint"):
            self.write("CLAUDE.md", "## mismagent\n- test: true\n- lint: true\n".replace(key + ": true", key + ": false"))
            code, out, err = self.mm("gate")
            self.assertEqual(code, 1, key)
            self.assertIn("%s: red" % key, out)
            self.assertIn(key, err)

    def test_gate_red_verdict_is_the_last_line_through_a_pipe(self):
        noise = "".join("echo noise-%d; " % i for i in range(40))
        self.write("CLAUDE.md", "## mismagent\n- test: %sfalse\n- lint: true\n" % noise)
        p = subprocess.run("%s %s gate 2>&1 | tail -3" % (sys.executable, MM), shell=True,
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(p.stdout.strip().splitlines()[-1], "gate: red (test)")

    def test_gate_times_out_and_kills_the_process_group(self):
        self.write("CLAUDE.md", "## mismagent\n- test: (trap '' TERM; sleep 3; touch late) >/dev/null 2>&1 & sleep 30\n"
                   "- lint: true\n- timeout: 1\n")  # the child ignores TERM and holds no pipe: KILL must reach it
        started = time.time()
        code, out, err = self.mm("gate")
        self.assertEqual(code, 1)
        self.assertLess(time.time() - started, 15)
        self.assertIn("test: red (timed out after 1 s: `timeout:` in CLAUDE.md ## mismagent)", out)
        self.assertIn("gate red: test", err)
        time.sleep(4)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "late")))  # the command's child died with it

    def test_gate_red_on_missing_config_or_check(self):
        self.write("CLAUDE.md", "# nothing\n")
        self.assertEqual(self.mm("gate")[0], 1)
        self.write("CLAUDE.md", CLAUDE)
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-1 | dup | x | y | R | Q | R0 |\n")
        code, _, err = self.mm("gate")
        self.assertEqual(code, 1)
        self.assertIn("check", err)


class Tag(Repo):
    def test_tag(self):
        self.slice("01-cart")
        self.commit()
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("not done", err)
        self.assertEqual(self.mm("tag", "R9")[0], 1)
        shutil.rmtree(os.path.join(self.dir, ".mismagent/slices"))
        self.done_release()
        self.review("R0-1", "HEALTHY")
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("cat-file", "-t", "R0"), "tag")  # annotated
        self.assertEqual(self.git("log", "-1", "--format=%s", "R0"), "review: R0")
        self.assertIn(".mismagent/reviews/R0-1.md", self.git("show", "--name-only", "--format=", "R0^{commit}"))
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.mm("tag", "R0")[0], 1)

    def test_tag_refuses_an_example_in_no_slice(self):
        self.done_release()
        self.write(".mismagent/examples/pay.md", "| id | given | when | then | rule | req | release |\n"
                   "| EX-4 | a cart | pay | paid | R | Q3 | R0 |\n")
        self.review("R0-1", "HEALTHY")
        self.commit()
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("EX-4 in no slice", err)
        self.assertEqual(self.git("tag", "-l"), "")

    def test_tag_refuses_red_gate(self):
        self.done_release()
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: false"))
        self.commit()
        self.review("R0-1", "HEALTHY")  # a review at HEAD: the gate alone refuses
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("gate red: test", err)
        self.assertEqual(self.git("tag", "-l"), "")

    def test_tag_refuses_without_a_review_at_head(self):
        self.done_release()
        self.review("R0-1", "HEALTHY")
        self.commit("later")  # HEAD moved past the review
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("R0: no release review at HEAD", err)
        self.assertEqual(self.git("tag", "-l"), "")

    def test_tag_of_a_design_pass_review_needs_why_and_writes_a_decision(self):
        self.done_release()
        self.review("R0-1", "DESIGN-PASS")
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("R0: review 1 is DESIGN-PASS: `tag R0 --why", err)
        self.assertEqual(self.git("tag", "-l"), "")
        code, _, err = self.mm("tag", "R0", "--why", "the two findings are cosmetic; R1 takes them")
        self.assertEqual(code, 0, err)
        decision = self.read(".mismagent/decisions/0001-confirm-R0.md")
        self.assertIn("the two findings are cosmetic; R1 takes them", decision)
        self.assertIn("- .mismagent/reviews/R0-1.md at", decision)
        self.assertIn(".mismagent/decisions/0001-confirm-R0.md", self.git("show", "--name-only", "--format=", "R0^{commit}"))
        self.assertIn("review 1 DESIGN-PASS", self.git("tag", "-n1", "-l", "R0"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_tag_refuses_open_questions(self):
        self.done_release()
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\n- hide the POIs?\n")
        self.commit("design pass")
        self.review("R0-1", "HEALTHY")
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("R0: 1 open question(s) in .mismagent/releases/R0.md", err)
        self.assertEqual(self.git("tag", "-l"), "")


class Check(Repo):
    def assertWarning(self, fragment, *args):
        code, out, err = self.check(*args)
        self.assertEqual(code, 0, err)
        self.assertIn("warning: " + fragment, out)

    def assertError(self, fragment, *args):
        code, out, err = self.check(*args)
        self.assertEqual(code, 1, out)
        self.assertIn(fragment, out)
        self.assertTrue(err.strip())

    def test_ok(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def release_file(self, rel="R0", questions=""):
        self.write(".mismagent/releases/%s.md" % rel, "# %s\n\nGoal.\n\n## Open questions\n%s" % (rel, questions))

    def test_release_spec_holds_together(self):
        self.slice("01-cart", examples="EX-1, EX-2")
        self.release_file(questions="none\n")
        code, out, _ = self.check("--release", "R0")
        self.assertEqual(code, 0, out)
        self.assertNotIn("R0:", out)

    def test_release_spec_problems_are_errors_for_that_release_only(self):
        self.slice("01-cart", examples="EX-1")
        self.slice("02-pay", examples="")
        self.release_file(questions="- what if the card is refused?\n")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)  # a warning, one line a release
        warned = [l for l in out.splitlines() if l.startswith("warning: R0:")]
        self.assertEqual(len(warned), 1, out)
        for fragment in ("EX-2 is in no slice", "02-pay.md: a feature slice names no example",
                         "1 open question line(s)"):
            self.assertIn(fragment, warned[0])
        self.assertIn("warning: R1: EX-3 is in no slice", out)
        code, out, _ = self.check("--release", "R0")
        self.assertEqual(code, 1, out)
        self.assertIn("error: R0: EX-2 is in no slice", out)
        self.assertNotIn("error: R1", out)

    def test_release_spec_needs_its_release_file(self):
        self.slice("01-cart", examples="EX-1, EX-2")
        self.assertError("no .mismagent/releases/R0.md", "--release", "R0")
        self.assertError("R7: no example and no slice names this release", "--release", "R7")

    def test_superseded_example_needs_no_slice(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES.replace("| 0 items|", "| 0 items (superseded by EX-1)|")
                   .replace("|0 items|", "|0 items (superseded by EX-1)|"))
        self.slice("01-cart", examples="EX-1")
        self.release_file()
        code, out, _ = self.check("--release", "R0")
        self.assertEqual(code, 0, out)

    def refactor(self, state, declared="Behavior change: offline languages come from the copies.\n"):
        self.write(".mismagent/slices/%s/05-tidy.md" % state, slice_text(kind="refactor", examples="")
                   .replace("Examples", "Base: abc1234\n" + declared + "Examples"))

    def test_an_unfinished_refactor_cannot_declare_a_behavior_change(self):
        for state in ("todo", "doing"):
            self.refactor(state)
            self.assertError("05-tidy.md: a refactor changes no behavior: the change is a fix or a feature with an "
                             "example (a ## Question for specify), or is reverted")
            os.remove(os.path.join(self.dir, ".mismagent/slices/%s/05-tidy.md" % state))
        self.refactor("doing", declared="")
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_a_done_refactor_with_a_behavior_change_is_history(self):
        self.refactor("done")
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_a_fix_slice_names_its_example(self):
        self.slice("01-cart", examples="EX-1, EX-2")
        self.slice("02-bug", kind="fix", examples="")
        self.release_file()
        self.assertError("02-bug.md: a fix slice names no example", "--release", "R0")

    def test_tagged_release_is_not_warned(self):
        self.slice("01-cart", examples="EX-1")
        self.commit()
        self.git("tag", "R0")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("warning: R0", out)

    def test_malformed_examples(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q |\n")
        self.assertError("6 columns")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| E-4 | x | y | z | R | Q | R0 |\n")
        self.assertError("is not EX-<n>")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q |  |\n")
        self.assertError("no release")

    def test_duplicate_ids(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-2 | x | y | z | R | Q | R1 |\n")
        self.assertError("duplicate example id EX-2 (.mismagent/examples/cart.md, .mismagent/examples/cart.md)")
        self.write(".mismagent/examples/cart.md", EXAMPLES)
        self.write(".mismagent/examples/search.md", EXAMPLES.split("|EX-2")[0].replace("EX-1", "EX-2"))
        self.assertError("duplicate example id EX-2 (.mismagent/examples/cart.md, .mismagent/examples/search.md)")

    def test_examples_by_capability_and_the_old_single_file(self):
        self.write(".mismagent/examples/search.md", "| id | given | when | then | rule | req | release |\n"
                   "|---|---|---|---|---|---|---|\n| EX-9 | a | b | c | R | Q | R1 |\n")
        self.slice("02-search", examples="EX-9")
        self.assertEqual(self.check()[0], 0, self.check()[1])
        os.remove(os.path.join(self.dir, ".mismagent/examples/search.md"))
        self.assertError("example EX-9 is not in .mismagent/examples/")
        os.remove(os.path.join(self.dir, ".mismagent/examples/cart.md"))
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-9 | a | b | c | R | Q | R1 |\n")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn(".mismagent/examples.md is one table for the whole product: split it by capability", out)

    def test_bad_slice_headers(self):
        self.slice("01-cart", kind="epic")
        self.assertError("Kind 'epic'")
        self.slice("01-cart", examples="EX-7")
        self.assertError("EX-7 is not in .mismagent/examples/")
        self.slice("01-cart", release="")
        self.assertError("no Release")
        os.remove(os.path.join(self.dir, ".mismagent/slices/todo/01-cart.md"))
        self.slice("01-cart", state="doing")
        self.assertError("without Base")

    def test_done_example_needs_marker(self):
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(examples="EX-1, EX-2").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "# EX-1\n# EX-12\n# noqa: E501\n")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppressions: 1"))
        self.assertError("EX-2 has no acceptance marker")
        self.acceptance("test_cart.py", "# EX-1 EX-2\n")
        self.assertEqual(self.check()[0], 0)

    def test_superseded_example_needs_no_marker(self):
        self.write(".mismagent/examples/cart.md",
                   EXAMPLES.replace("|0 items|", "|0 items (superseded by EX-3)|"))
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(examples="EX-1, EX-2").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "# EX-1\n")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_suppressions(self):
        self.write("src/a.py", "import os  # noqa: F401\nx = 1  # EX-1 marker, not a suppression\n")
        self.commit()
        self.assertError("suppression markers: 1 > suppressions 0")
        self.write("CLAUDE.md", CLAUDE + "\n## mismagent\n- suppressions: 1\n")
        self.assertEqual(self.check()[0], 0)
        self.write("src/b.ts", "// eslint-disable-next-line\nlet y: any = 1 // @ts-ignore\n")
        self.write("src/c.py", "z = f()  # type: ignore\n")
        self.commit()
        self.assertError("suppression markers: 3 > suppressions 1")

    def test_markers_not_confused_with_codes(self):
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(examples="EX-1").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "x = 1  # noqa: E501, E1\n")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppressions: 5"))
        self.assertError("EX-1 has no acceptance marker")
        self.acceptance("test_cart.py", "x = 1  # noqa: E501 EX-10\n")
        self.assertError("EX-1 has no acceptance marker")

    def test_doing_slice_under_review_needs_its_markers(self):
        self.started()
        base = self.git("rev-parse", "HEAD")
        self.git("rm", "-q", "tests/acceptance/test_01-cart.py")
        self.write("src/cart.py", "x = 1\n")
        self.commit("01-cart: code, marker dropped")
        self.assertEqual(self.check()[0], 0)  # while building: no marker required yet
        self.assertError("01-cart.md: doing, but EX-1 has no acceptance marker", "--base", base)
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("acc")
        self.assertEqual(self.check("--base", base)[0], 0)

    def test_acceptance_folders_from_claude_md(self):
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400",
                                               "- max_file_lines: 400\n- acceptance: `app/src/acc`, `web/acc/`"))
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(examples="EX-1, EX-2").replace("Examples", "Base: abc1234\nExamples"))
        self.write("app/src/acc/CartTest.kt", "// EX-1\n")
        self.write("tests/acceptance/test_cart.py", "# EX-2\n")  # not a configured folder
        self.commit()
        self.assertError("EX-2 has no acceptance marker under app/src/acc, web/acc/")
        self.write("web/acc/cart.test.js", "// EX-2\n")
        self.commit()
        self.assertEqual(self.check()[0], 0)

    def test_convention_topic_required_sections(self):
        topic = ".claude/skills/conventions/references/message.md"
        self.write(topic, "# message\n\n## Where\nsrc/<m>/Contracts/\n\n## Shape\n```\n## Uses\n```\n"
                          "##\nMust is prose\n## Never-ever\nx\n")
        self.assertError("message.md: no ## Uses, ## Must, ## Never, ## Example (a kind of code has")
        self.write(topic, "".join("  ## %s ##\nx\n" % s for s in ("Where", "Uses", "Shape", "Must", "Never", "Example")))
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_convention_practice_needs_must_and_never(self):
        practice = ".claude/skills/conventions/references/practices/doubts.md"
        self.write(practice, "# doubts\n\n## Must\n- a design doubt goes to a second model first\n")
        self.assertError("practices/doubts.md: no ## Never (a practice has ## Must, ## Never)")
        self.write(practice, "# doubts\n\n## Must\n- ask\n## Never\n- guess\n")
        self.assertEqual(self.check()[0], 0)

    def test_convention_topic_where_names_folders_to_come(self):
        topic = ".claude/skills/conventions/references/message.md"
        body = ("## Where\n`src/contracts/` — one file per message\n## Uses\nnone\n## Shape\n" + "word " * 500 +
                "\n## Must\n- a CorrelationId\n## Never\n- logic\n## Example\n%s\n")
        self.write(topic, body % "none yet: the library's docs")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)  # a folder to come, and no word cap
        self.assertNotIn("words", out)
        self.write(topic, body % "`src/contracts/order_placed.py`")
        self.assertError("message.md: cites src/contracts/order_placed.py, which does not exist")

    def test_long_brief_passes(self):
        self.write(".mismagent/brief.md", "word " * 5000)
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("brief.md", out)

    def test_max_file_lines(self):
        self.write("CLAUDE.md", CLAUDE.replace("400", "3"))
        self.write("src/big.py", "a = 1\n" * 4)
        self.write("docs/long.md", "line\n" * 50)
        self.write("src/untracked.py", "a = 1\n" * 10)
        self.write("tests/test_big.py", "a = 1\n" * 10)
        self.git("add", "src/big.py", "docs/long.md", "CLAUDE.md", "tests/test_big.py")
        self.git("commit", "-qm", "big")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("src/big.py: 4 lines > max_file_lines 3", out)
        self.assertNotIn("long.md", out)
        self.assertNotIn("untracked.py", out)
        self.assertNotIn("test_big.py", out)

    def test_a_gate_setting_changed_since_base_is_warned_for_the_reviewer(self):
        base = self.commit("base")
        self.write("src/big.py", "import os  # noqa: F401\n" + "x = 1\n" * 451)
        self.commit("01-cart: big")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 1)
        self.assertIn("src/big.py: 452 lines > max_file_lines 400", out)
        self.assertIn("suppression markers: 1 > suppressions 0", out)
        self.assertNotIn("the gate's own setting", out)  # nothing changed in CLAUDE.md
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- max_file_lines: 2000\n- suppressions: 5"))
        self.commit("01-cart: room for it")  # the builder loosens its own gate
        code, out, err = self.check("--base", base)
        self.assertEqual(code, 0, out + err)  # green, a migration changes them too — but said, one line a key
        self.assertIn("warning: CLAUDE.md ## mismagent: `max_file_lines:` changed since %s (was 400, now 2000) — the "
                      "gate's own setting: the reviewer judges it against `git show %s:CLAUDE.md`" % (base, base[:12]), out)
        self.assertIn("warning: CLAUDE.md ## mismagent: `suppressions:` changed since %s (was unset, now 5)" % base, out)
        self.assertEqual(out.count("the gate's own setting"), 2)
        self.assertNotIn("the gate's own setting", self.check()[1])  # no base: nothing to compare with
        loosened = self.head()
        self.write("CLAUDE.md", self.read("CLAUDE.md").replace("- smoke: true", "- smoke: true\n- shot: true"))
        self.commit("01-cart: shot")  # the builder is told to write it
        self.assertNotIn("the gate's own setting", self.check("--base", loosened)[1])
        self.write("CLAUDE.md", self.read("CLAUDE.md").replace("- suppressions: 5\n", "").replace("-   lint :  `true`", "- lint: true"))
        out = self.check("--base", loosened)[1]  # uncommitted too; `lint` is the same value, written another way
        self.assertIn("warning: CLAUDE.md ## mismagent: `suppressions:` changed since %s (was 5, now unset)" % loosened, out)
        self.assertEqual(out.count("the gate's own setting"), 1)

    def test_no_claude_md_at_base_had_no_setting(self):
        self.git("rm", "-q", "CLAUDE.md")
        base = self.commit("no settings yet")
        self.write("CLAUDE.md", CLAUDE)
        self.commit("skeleton")
        out = self.check("--base", base)[1]
        self.assertEqual(out.count("the gate's own setting"), 4)  # test, lint, smoke, max_file_lines
        self.assertIn("`test:` changed since %s (was unset, now true)" % base, out)

    def test_the_stacks_own_suppression_markers(self):
        self.write("src/a.py", "x = 1\n")
        self.write("web/app.js", "let a = 1\n")
        self.commit()
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("suppress:", out)  # the built-in markers cover these
        self.write("App/View.swift", "// swiftlint:disable force_cast\nlet a = b as! C // @ts-ignore\n"
                   "#[allow(dead_code)]\n@Suppress(\"x\")\n// @ts-expect-error\n#pragma warning disable\n")
        self.write("App/Model.kt", "val a = 1\n")
        self.write("scripts/run.sh", "# shellcheck disable=SC2086\necho $x\n")  # a shell script has its own too
        self.commit()
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)  # blind there, and no project turns red on an upgrade — but said, once
        self.assertEqual(out.count("no suppress:"), 1)
        self.assertIn("warning: CLAUDE.md ## mismagent: no suppress: — the built-in suppression markers are those of "
                      "Python, JavaScript, Go and Java, and 3 tracked source file(s) are in other languages (.kt, .sh, "
                      ".swift): `suppress: <markers>` names this stack's own, comma-separated", out)
        own = "swiftlint:disable, `@ts-ignore`, @ts-expect-error , #[allow(,@Suppress(, #pragma warning disable"
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppress: %s" % own))
        self.assertError("suppression markers: 6 > suppressions 0")  # a line with two of them is one line
        self.assertNotIn("no suppress:", self.check()[1])
        self.write("src/a.py", "import os  # noqa: F401\n")  # the built-in ones still count, beside the stack's
        self.assertError("suppression markers: 7 > suppressions 0")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppress: %s\n- suppressions: 7" % own))
        self.assertEqual(self.check()[0], 0)
        for none in ("none", "-"):  # the stack has no marker of its own: said, so not warned
            self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppress: %s\n- suppressions: 1" % none))
            code, out, _ = self.check()
            self.assertEqual(code, 0, out)
            self.assertNotIn("suppress:", out)

    def test_a_suppression_marker_is_plain_text_never_a_pattern(self):
        self.write("App/View.swift", "let aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa! = 1\nlet x = 1\n")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- timeout: 1\n- suppress: `(a+)+$`, (?=x)"))
        self.commit()
        code, out, _ = self.check()  # as a pattern the first would hang the gate, the second count `let x`
        self.assertEqual(code, 0, out)
        self.write("App/View.swift", "let a = 1 // (a+)+$\n")
        self.assertError("suppression markers: 1 > suppressions 0")
        for short in ("//", "#"):
            self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- suppress: swiftlint:disable, %s" % short))
            self.assertError("CLAUDE.md ## mismagent: suppress: %r is too short for a marker (4 characters at least)" % short)

    def test_test_folders_have_no_size_limit(self):
        settings = CLAUDE.replace("400", "3").replace("- smoke: true", "- smoke: true\n- suppress: none")
        self.write("CLAUDE.md", settings)
        self.write("AppTests/CartTests.swift", "let a = 1\n" * 10)
        self.write("app/src/test/kotlin/CartTest.kt", "val a = 1\n" * 10)
        self.write("Features/Cart.swift", "let a = 1\n" * 10)
        self.commit()
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        for rel in ("AppTests/CartTests.swift", "app/src/test/kotlin/CartTest.kt", "Features/Cart.swift"):
            self.assertIn("%s: 10 lines > max_file_lines 3" % rel, out)
        self.write("CLAUDE.md", settings + "\n## mismagent\n- tests: `AppTests`, app/src/test/\n- acceptance: Features\n")
        code, out, _ = self.check()
        self.assertNotIn("Tests.swift", out)
        self.assertNotIn("CartTest.kt", out)
        self.assertNotIn("Features/Cart.swift", out)  # an acceptance folder is a test folder
        self.assertEqual(code, 0, out)

    def test_another_examples_test_edited_is_a_warning_naming_the_file(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z (superseded by EX-3) | R | Q | R1 |\n")
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        self.acceptance("test_old.py", "# EX-4\n")
        base = self.commit("acc")
        self.slice("02-more", state="doing", examples="EX-2")
        path = ".mismagent/slices/doing/02-more.md"
        self.write(path, self.read(path).replace("Examples", "Base: %s\nExamples" % base))
        self.acceptance("test_new.py", "# EX-2\n")
        self.commit("added")
        self.assertNotIn("warning: tests/", self.check("--base", base)[1])
        self.acceptance("test_old.py", "# EX-4 dropped\n")  # a superseded example: allowed
        self.acceptance("test_other.py", "# EX-3 EX-2 shared\n" + "x = 1\n" * 20)  # names EX-2: the slice's own
        self.assertNotIn("warning: tests/", self.check("--base", base)[1])
        self.acceptance("test_other.py", "# EX-3 weakened\n" + "x = 1\n" * 20)
        self.assertWarning("tests/acceptance/test_other.py: acceptance file modified since %s, naming no example "
                           "of 02-more: the reviewer judges it against `git show %s:tests/acceptance/test_other.py`"
                           % (base, base[:12]), "--base", base)
        self.write(path, self.read(path).replace("Kind: feature", "Kind: refactor"))
        self.assertNotIn("warning: tests/", self.check("--base", base)[1])  # a refactor adapts them by nature
        self.write(path, self.read(path).replace("Kind: refactor", "Kind: fix"))
        self.assertWarning("tests/acceptance/test_other.py: acceptance file modified", "--base", base)  # a fix too
        self.write(path, self.read(path).replace("Kind: fix", "Kind: feature"))
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        self.git("mv", "tests/acceptance/test_other.py", "tests/acceptance/test_renamed.py")
        self.acceptance("test_renamed.py", "# EX-3\n" + "x = 1\n" * 19 + "x = 2\n")
        self.commit("rename and edit")
        self.assertWarning("tests/acceptance/test_renamed.py: acceptance file renamed and edited since", "--base", base)

    def test_a_shared_helper_or_fixture_change_is_a_warning(self):
        self.acceptance("conftest.py", "helper = 1\n")
        self.write("tests/acceptance/fixtures/doc.bin", "v1")
        base = self.commit("acc")
        self.started(name="02-more", examples="EX-2")
        self.acceptance("conftest.py", "helper = 2\n")
        self.write("tests/acceptance/fixtures/doc.bin", "v2")
        self.commit("02-more: helper and fixture")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 0)
        self.assertIn("warning: tests/acceptance/conftest.py: acceptance file modified since", out)
        self.assertIn("warning: tests/acceptance/fixtures/doc.bin: acceptance file modified since", out)

    def test_a_deleted_acceptance_file_is_listed(self):
        self.acceptance("test_other.py", "# EX-3\n")
        base = self.commit("acc")
        self.started(name="02-more", examples="EX-2")
        self.git("rm", "-q", "tests/acceptance/test_other.py")
        self.commit("02-more: dropped a test")
        self.assertWarning("tests/acceptance/test_other.py: acceptance file deleted since", "--base", base)

    def test_base_pure_rename_allowed(self):
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        base = self.commit("acc")
        self.started(name="02-more", examples="EX-2")
        self.git("mv", "tests/acceptance/test_other.py", "tests/acceptance/test_moved.py")
        self.acceptance("test_new.py", "# EX-2\n")
        self.commit("move")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 0)
        self.assertNotIn("test_moved.py", out)  # a pure rename is neither an error nor a warning

    def test_base_requirements_changed(self):
        self.write("REQUISITI.md", "v1\n")
        self.write("requirements.txt", "flask\n")
        base = self.commit("reqs")
        self.write("requirements.txt", "flask\ndjango\n")
        self.commit()
        self.assertEqual(self.check("--base", base)[0], 0)
        self.write("REQUISITI.md", "v2\n")
        self.assertError("REQUISITI.md: changed since", "--base", base)
        self.write("REQUISITI.md", "v1\n")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit()
        self.assertError(".mismagent/examples/cart.md: changed since", "--base", base)
        self.write(".mismagent/examples/cart.md", EXAMPLES)
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nmore\n")
        self.commit()
        self.assertError(".claude/skills/conventions/SKILL.md: changed since", "--base", base)

    def test_base_human_commits_are_not_the_builders(self):
        base = self.commit("base")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit("specify R1: EX-4 (the human)")
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nmore\n")
        self.commit("conventions after slice 01")
        self.git("revert", "--no-edit", "HEAD")
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-5 | x | y | z | R | Q | R1 |\n")
        self.assertError(".mismagent/examples/cart.md: changed since", "--base", base)  # uncommitted
        self.commit("01-cart: work")
        self.assertError(".mismagent/examples/cart.md: changed since", "--base", base)

    def test_base_a_lookalike_subject_is_not_the_human(self):
        base = self.commit("base")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit("conventions-fix slice 01")
        self.assertError(".mismagent/examples/cart.md: changed since", "--base", base)

    def test_base_a_human_subject_on_code_is_not_the_human(self):
        base = self.commit("base")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.write("src/cart.py", "x = 2\n")
        self.commit("specify R1: EX-4")
        self.assertError(".mismagent/examples/cart.md: changed since", "--base", base)

    def test_base_a_rename_by_the_human_keeps_the_builders_edit(self):
        base = self.commit("base")
        self.write(".mismagent/examples/cart.md", EXAMPLES.replace("EX-1", "EX-1 ") + "\n" * 30)
        self.commit("01-cart: weaken")
        self.git("mv", ".mismagent/examples/cart.md", ".mismagent/examples/basket.md")
        self.commit("specify R1: rename")
        self.assertError("changed since", "--base", base)

    def test_base_staged_or_untracked_is_not_the_human(self):
        self.write("REQUISITI.md", "v1\n")
        base = self.commit("base")
        self.write("REQUISITI.md", "v2\n")
        self.commit("specify R1: v2")
        self.write("REQUISITI.md", "v3\n")
        self.git("add", "REQUISITI.md")
        self.write("REQUISITI.md", "v2\n")
        self.assertError("REQUISITI.md: changed since", "--base", base)

    def test_base_not_an_ancestor_exempts_nothing(self):
        base = self.commit("base")
        self.git("checkout", "-q", "-b", "side")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-9 | x | y | z | R | Q | R1 |\n")
        side = self.commit("specify R1: side")
        self.git("checkout", "-q", "-")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit("specify R1: EX-4")
        self.assertError("changed since", "--base", side)

    def test_base_a_revert_with_a_net_change_is_the_human(self):
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nv1\n")
        base = self.commit("base")
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nv2\n")
        self.commit("conventions after slice 01")
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nv3\n")
        self.commit("conventions after slice 02")
        self.git("revert", "--no-edit", "HEAD")
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])

    def test_a_reverted_builder_edit_does_not_taint_a_later_human_change(self):
        skill = ".claude/skills/conventions/SKILL.md"
        self.write(skill, "---\nname: conventions\n---\nv1\n")
        base = self.commit("base")
        self.write(skill, "---\nname: conventions\n---\nv2\n")
        self.commit("01-cart: touched the skill")
        self.git("revert", "--no-edit", "HEAD")
        self.write(skill, "---\nname: conventions\n---\nv3\n")
        self.commit("conventions after slice 01")
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])

    def test_a_hand_undone_builder_edit_is_neutral(self):
        skill = ".claude/skills/conventions/SKILL.md"
        self.write(skill, "---\nname: conventions\n---\nv1\n")
        base = self.commit("base")
        self.write(skill, "---\nname: conventions\n---\nv2\n")
        self.commit("01-cart: touched the skill")
        self.write(skill, "---\nname: conventions\n---\nv1\n")
        self.commit("01-cart: put it back")
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])
        self.write(skill, "---\nname: conventions\n---\nv3\n")
        self.commit("conventions after slice 01")
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])

    def test_an_edit_under_an_intermediate_name_is_still_the_builders(self):
        base = self.commit("base")
        self.git("mv", ".mismagent/examples/cart.md", ".mismagent/examples/basket.md")
        self.commit("specify R1: basket")
        self.write(".mismagent/examples/basket.md", EXAMPLES.replace("1 item", "0 items"))
        edit = self.commit("01-cart: weaken")
        self.git("mv", ".mismagent/examples/basket.md", ".mismagent/examples/trolley.md")
        self.commit("specify R1: trolley")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 1)
        self.assertIn("trolley.md: changed since %s by %s 01-cart: weaken" % (base, edit[:7]), out)

    def test_a_builder_edit_redone_after_a_revert_is_still_the_builders(self):
        skill = ".claude/skills/conventions/SKILL.md"
        self.write(skill, "---\nname: conventions\n---\nv1\n")
        base = self.commit("base")
        self.write(skill, "---\nname: conventions\n---\nv2\n")
        self.commit("01-cart: touched the skill")
        self.git("revert", "--no-edit", "HEAD")
        self.write(skill, "---\nname: conventions\n---\nv2\n")
        again = self.commit("01-cart: again")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 1)
        self.assertIn("SKILL.md: changed since %s by %s 01-cart: again (the human's file" % (base, again[:7]), out)

    def test_bad_base_ref(self):
        self.assertEqual(self.check("--base", "no-such-ref")[0], 1)

    def test_check_warns_on_notes_that_are_not_notes(self):
        self.write(".mismagent/design-notes.md", "# Design notes\n- a note\n  that goes on\n\n1. parked\n2. parked too\n"
                   "Le note in sosta sono elenchi numerati.\n")
        self.assertWarning(".mismagent/design-notes.md: 3 line(s) that are not notes (a note is one `- ` line; "
                           "headings, blank and indented lines are fine), from '1. parked'")
        self.write(".mismagent/design-notes.md", "# Design notes\n- a note\n  that goes on\n\n- RISK: x\n")
        self.assertNotIn("not notes", self.check()[1])

    def test_proposal_counts_are_untouched(self):
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n- create errors: typed\n1. not a proposal\n")
        self.assertIn('"proposals": 1', self.mm("status", "--json")[1])

    def test_check_warns_on_a_missing_smoke(self):
        self.write("CLAUDE.md", CLAUDE.replace("- smoke: true\n", ""))
        self.assertWarning("CLAUDE.md ## mismagent: no smoke:")

    def test_a_bad_timeout_value_is_a_check_error(self):
        for bad in ("0", "soon", "-5"):
            self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", "- timeout: %s\n- max_file_lines" % bad))
            self.assertError("CLAUDE.md ## mismagent: timeout: %r is not a positive number of seconds" % bad)
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", "- timeout: 5\n- max_file_lines"))
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_decision_without_evidence_warns(self):
        self.write(".mismagent/decisions/0001-stack.md", "# Stack\nPython.\n")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("no Evidence", out)
        self.write(".mismagent/decisions/0002-store.md", "# Store\nSQLite.\n")
        warned = [line for line in self.check()[1].splitlines() if "no Evidence" in line]
        self.assertEqual(len(warned), 1, warned)
        self.assertIn("2 decision(s)", warned[0])
        self.assertIn("0001-stack.md, 0002-store.md", warned[0])
        self.write(".mismagent/decisions/0001-stack.md", "# Stack\nPython.\n\nEvidence: python3 --version\n")
        self.write(".mismagent/decisions/0002-store.md", "# Store\nSQLite.\n\nEvidence: ls\n")
        self.assertNotIn("no Evidence", self.check()[1])

    def test_no_word_cap(self):
        self.write(".mismagent/progress.md", "word " * 20000)
        code, out, _ = self.check()
        self.assertEqual(code, 0)
        self.assertNotIn("compact", out)

    def test_skill_cites_missing_file(self):
        self.write("src/cart.py", "x = 1\n")
        self.write(".claude/skills/conventions/SKILL.md",
                   "Errors: `references/practices/errors.md`. Model: `src/cart.py`, not `x.y`.\n")
        self.write(".claude/skills/conventions/references/practices/errors.md",
                   "## Must\nSee `src/errors.py` and `tests/acceptance/`.\n## Never\nx\n")
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("cites src/errors.py", out)
        self.assertIn("cites tests/acceptance/", out)
        self.assertNotIn("cart.py", out)
        self.assertNotIn("practices/errors.md,", out)
        self.write("src/errors.py", "y = 2\n")
        os.makedirs(os.path.join(self.dir, "tests/acceptance"), exist_ok=True)
        self.assertEqual(self.check()[0], 0)


SHOT = ('- shot: for n in $MM_DESIGN; do [ "$n" = Gone ] || printf png > "$MM_SHOTS/$n.png"; done\n')


class Design(Repo):
    """Design: names the artboards a slice must look like; mm built proves the look with a screen each."""

    def designed(self, design="Verde.png", shot=True):
        self.write(".mismagent/design/Verde.png", "png")
        self.write(".mismagent/design/Rosso.png", "png")
        if shot:
            self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", SHOT + "- max_file_lines"))
        self.slice("01-cart", extra="", examples="EX-1\nDesign: " + design)
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("specify R0")

    def test_check_refuses_an_artboard_it_cannot_read(self):
        for ref, why in (("https://claude.ai/artifact/x", "is a link"), ("Verde.html", "is not an image"),
                         ("Giallo.png", "does not exist under .mismagent/design/"),
                         ("../../CLAUDE.md.png", "does not exist")):
            self.designed(ref)
            code, out, _ = self.check()
            self.assertEqual(code, 1, ref)
            self.assertIn("Design: %s %s" % (ref, why), out)
        self.designed("Verde.png, .mismagent/design/Rosso.png")
        self.assertEqual(self.check()[0], 0, self.check()[1])

    def test_built_renders_a_screen_per_artboard_on_disk_never_committed(self):
        self.designed("Verde.png Rosso.png")
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        code, out, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 0, err)
        self.assertIn(".mismagent/design/Verde.png  <->  .mismagent/shots/01-cart/Verde.png", out)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, ".mismagent/shots/01-cart/Rosso.png")))
        self.assertEqual(self.git("ls-files", ".mismagent/shots"), "")  # a set per round would bloat the history
        self.assertEqual(self.next()["action"], "review")  # on disk, not dirty
        self.git("add", "-A")  # the builder's commit at a green, in a project with no .gitignore for them
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_built_refuses_a_staged_shot(self):
        self.designed("Verde.png")
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        self.write(".mismagent/shots/01-cart/Verde.png", "png")
        self.git("add", "-f", ".mismagent/shots")
        code, _, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 1)
        self.assertIn("1 shot(s) staged (.mismagent/shots/01-cart/Verde.png)", err)

    def test_tag_commits_the_release_shots_past_a_gitignore(self):
        self.designed("Verde.png")
        self.write(".mismagent/slices/done/01-cart.md", self.read(".mismagent/slices/todo/01-cart.md")
                   .replace("Examples", "Base: abc1234\nExamples").replace("EX-1\n", "EX-1, EX-2\n"))
        os.remove(os.path.join(self.dir, ".mismagent/slices/todo/01-cart.md"))
        self.acceptance("test_cart.py", "# EX-1 EX-2\n")
        self.commit("done")
        self.assertEqual(self.mm("shot", "R0")[0], 0)
        self.write(".mismagent/reviews/R0.draft.md", "same\n")
        self.assertEqual(self.mm("review", "R0", "HEALTHY", "--sha", self.head(), "--look", "0")[0], 0)
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 0, err)
        self.assertIn(".mismagent/shots/R0/Verde.png", self.git("show", "--name-only", "--format=", "R0^{commit}"))

    def test_check_warns_on_slice_shots_still_tracked(self):
        self.designed("Verde.png")
        self.write(".mismagent/shots/01-cart/Verde.png", "png")
        self.write(".mismagent/shots/R0/Verde.png", "png")
        self.commit("shots committed by an older mm")
        out = self.check()[1]
        self.assertIn("1 slice shot set(s) tracked in git (01-cart)", out)
        self.assertIn("git rm -r --cached .mismagent/shots/01-cart", out)
        self.assertNotIn("shots/R0", out)  # a release's set is kept

    def test_built_refuses_without_the_screens(self):
        self.designed(shot=False)
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        self.assertIn("no `shot` in CLAUDE.md", self.mm("built", "01-cart", "--friction", "none")[2])
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", SHOT + "- max_file_lines"))
        self.commit("01-cart: shot command")
        self.write(".mismagent/design/Gone.png", "png")
        self.write(".mismagent/slices/doing/01-cart.md", self.read(".mismagent/slices/doing/01-cart.md")
                   .replace("Design: Verde.png", "Design: Verde.png Gone.png"))
        self.commit("specify R0: Gone")  # the human's: an artboard and the slice, nothing else
        self.assertIn("shot wrote no Gone.png", self.mm("built", "01-cart", "--friction", "none")[2])
        self.assertNotIn("Built:", self.read(".mismagent/slices/doing/01-cart.md"))

    def test_shot_timeout_publishes_no_partial_screens(self):
        self.designed("Verde.png Rosso.png")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", '- shot: printf png > "$MM_SHOTS/Verde.png"; '
                                               "sleep 30\n- timeout: 1\n- max_file_lines"))
        self.commit("a slow shot")
        self.assertEqual(self.mm("start", "01-cart")[0], 0)
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        code, _, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 1)
        self.assertIn("shot: red (timed out after 1 s", err)
        self.assertFalse(os.path.isdir(os.path.join(self.dir, ".mismagent/shots/01-cart")))
        self.assertFalse(os.path.isdir(os.path.join(self.dir, ".mismagent/shots/01-cart.rendering")))
        self.assertNotIn("Built:", self.read(".mismagent/slices/doing/01-cart.md"))

    def test_shot_renders_a_release_and_tag_keeps_it(self):
        self.designed("Verde.png")
        self.slice("02-more", examples="EX-2\nDesign: Rosso.png Verde.png")
        self.commit("specify R0: 02")
        code, out, err = self.mm("shot", "R0")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count("<->"), 2)
        self.assertEqual(self.mm("shot", "01")[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, ".mismagent/shots/01-cart/Verde.png")))
        self.slice("03-plain", release="R1", examples="EX-3")
        self.commit("specify R1")
        self.assertIn("R1 names no artboard", self.mm("shot", "R1")[2])
        self.assertIn("R9 is neither a slice nor a release", self.mm("shot", "R9")[2])

    def test_the_artboards_are_the_humans(self):
        self.designed()
        base = self.head()
        self.write(".mismagent/design/Verde.png", "other")
        self.commit("01-cart: closer to the code")
        code, out, _ = self.check("--base", base)
        self.assertIn(".mismagent/design/Verde.png: changed since", out)


TOPIC = "# %s\n\n## Where\nsrc/\n## Uses\nnone\n## Shape\nx\n## Must\n- x\n## Never\n- y\n## Example\nnone yet\n"


class Categories(Repo):
    """Each kind topic of the conventions skill sits under one `## Kinds — <category>` of SKILL.md."""

    def skill(self, body):
        for kind in ("use-case", "errors", "acceptance-tests"):
            self.write(".claude/skills/conventions/references/%s.md" % kind, TOPIC % kind)
        self.write(".claude/skills/conventions/references/practices/pairing.md", "# p\n\n## Must\n- x\n## Never\n- y\n")
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\n\n" + body)
        self.commit("skill")
        return self.check()

    CATEGORIZED = ("## Kinds — local\n- use-case → `references/use-case.md` (src/app/)\n\n"
                   "## Kinds - cross-cutting\n- errors → references/errors.md\n\n"
                   "## Kinds — tests\n- acceptance-tests → `references/acceptance-tests.md`\n\n"
                   "## Practices\n- pairing → `references/practices/pairing.md`\n")

    def test_categorized_skill_is_green(self):
        code, out, _ = self.skill(self.CATEGORIZED)
        self.assertEqual(code, 0, out)
        self.assertNotIn("categor", out)

    def test_a_plain_kinds_section_is_only_warned(self):
        code, out, _ = self.skill("## Kinds\n- use-case → `references/use-case.md`\n- errors → `references/errors.md`\n"
                                  "- acceptance-tests → `references/acceptance-tests.md`\n")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: .claude/skills/conventions/SKILL.md: kinds not categorized", out)

    def test_a_topic_in_no_category_or_in_two_is_refused(self):
        code, out, _ = self.skill(self.CATEGORIZED.replace("- errors → references/errors.md\n", "")
                                  .replace("## Practices", "- use-case again → `references/use-case.md`\n\n## Practices"))
        self.assertEqual(code, 1)
        self.assertIn("references/errors.md: listed under no category", out)
        self.assertIn("references/use-case.md: listed under local and tests", out)
        self.assertNotIn("pairing.md: listed", out)

    def test_a_plain_kinds_beside_categories_is_refused(self):
        code, out, _ = self.skill(self.CATEGORIZED + "\n## Kinds\n- old\n")
        self.assertEqual(code, 1)
        self.assertIn("a plain ## Kinds beside the categorized ones", out)


class Friction(Repo):
    """The method's friction: one line per built round, optionally one per review; mm log counts them."""

    def test_built_requires_friction_checked_before_the_gate(self):
        self.started()
        self.write("src/cart.py", "x = 1\n")
        self.commit("code")
        self.assertEqual(self.mm("built", "01-cart")[0], 2)  # usage: --friction is required
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: sleep 5; false"))
        self.commit("slow red gate")
        for bad, why in (("mood: meh", "category one of spec"), ("spec: " + "w " * 16, "16 words, at most 15")):
            t0 = time.time()
            code, _, err = self.mm("built", "01-cart", "--friction", bad)
            self.assertEqual(code, 1)
            self.assertIn(why, err)
            self.assertLess(time.time() - t0, 4)  # refused before the gate ran
        self.write("CLAUDE.md", CLAUDE)
        self.commit("green")
        code, _, err = self.mm("built", "01-cart", "--friction", "Spec:  EX-1 does not say  what an empty cart shows")
        self.assertEqual(code, 0, err)
        text = self.read(".mismagent/slices/doing/01-cart.md")
        self.assertIn("Built: 1\nFriction: 1: spec: EX-1 does not say what an empty cart shows\n", text)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_rounds_add_lines_and_log_counts(self):
        self.started()
        self.work()
        self.review("01-cart-1", "REWORK")
        self.commit("review 1")
        self.write("src/cart.py", "x = 2\n")
        self.commit("rework")
        code, _, err = self.mm("built", "01-cart", "--friction", "tool: gate listed a file I never touched")
        self.assertEqual(code, 0, err)
        text = self.read(".mismagent/slices/doing/01-cart.md")
        self.assertIn("Built: 2\nFriction: 1: none\nFriction: 2: tool: gate listed a file I never touched", text)
        self.assertRegex(text, r"Friction: 2: [^\n]+\nGate: 1: \d+\nGate: 2: \d+\n")
        self.write(".mismagent/reviews/01-cart.draft.md", "all good\n")
        code, _, err = self.mm("review", "01-cart", "PASS", "--sha", self.head(),
                               "--friction", "review: the slice file had no Base after a rename")
        self.assertEqual(code, 0, err)
        self.assertIn("FRICTION: review: the slice file had no Base after a rename\n",
                      self.read(".mismagent/reviews/01-cart-2.md"))
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("status", "--porcelain"), "")
        code, out, err = self.mm("log")
        self.assertEqual(code, 0, err)
        self.assertIn("friction: 1 of 2 built rounds (50%) · tool 1 · review 1", out)
        self.assertIn("landed 1: rounds median 2 p75 2 · doubts 0 · wall-clock median 0 p75 0 min", out)
        self.assertIn("tool: 01-cart r2 (builder): gate listed a file I never touched", out)
        self.assertIn("review: 01-cart-2 (reviewer): the slice file had no Base after a rename", out)
        self.assertRegex(out, r"gate: 2 run\(s\) by mm built · median \d+ s p75 \d+ s max \d+ s")
        data = json.loads(self.mm("log", "--json", "--release", "R0")[1])
        self.assertEqual(data["friction"]["tool"], 1)
        self.assertEqual(data["landed"][0]["rounds"], 2)
        self.assertEqual(len(data["gate_seconds"]), 2)
        self.assertIn("no slice has Release: R9", self.mm("log", "--release", "R9")[2])

    def test_log_of_an_empty_repo(self):
        code, out, err = self.mm("log")
        self.assertEqual(code, 0, err)
        self.assertIn("friction: 0 of 0 built rounds (0%) · none", out)


class Map(Repo):
    """ARCHITECTURE.md is the map of the code as it is: check warns on what makes it a chronicle."""

    def test_map_warns_on_missing_paths_line_numbers_slices_and_size(self):
        self.write("App/Sources/Formato/Composizione.swift", "let x = 1\n")
        self.write("ARCHITECTURE.md", "# Architecture\n- `App/Sources/Formato/Composizione.swift` wires the app\n"
                   "- `Composizione.swift`, `Formato/`, `Sources/Formato` and `/usr/bin/swift` (outside)\n"
                   "- `project.yml`, `Form/` and `ResponseCache` (a symbol)\n"
                   "- the cache, ResponseCache.swift:20-27 and `WikimediaHTTP.swift:9,25`, since slice 81\n")
        self.commit("map")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)  # warnings: the reviewer judges the ones a diff caused
        self.assertIn("ARCHITECTURE.md cites Form/, project.yml, which no file", out)  # a segment, not a prefix
        self.assertIn("cites line numbers (ResponseCache.swift:20, WikimediaHTTP.swift:9)", out)
        self.assertIn("ARCHITECTURE.md names slices (slice 81)", out)
        self.assertNotIn("max_map_chars", out)
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines", "- max_map_chars: 100\n- max_file_lines"))
        self.assertIn("characters > max_map_chars 100", self.check()[1])

    def test_a_clean_map_is_quiet(self):
        self.write("src/cart.py", "x = 1\n")
        self.write("ARCHITECTURE.md", "# Architecture\n- `src/cart.py`: the cart, `Cart.add`\n")
        self.commit("map")
        self.assertNotIn("ARCHITECTURE.md", self.check()[1])


class Look(Repo):
    """A release review counts the artboard pairs that differ; tag records their acceptance."""

    def designed_release(self):
        self.write(".mismagent/design/Verde.png", "png")
        self.write(".mismagent/slices/done/01-cart.md", slice_text(examples="EX-1, EX-2\nDesign: Verde.png")
                   .replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "# EX-1 EX-2\n")
        self.commit("done")
        self.write(".mismagent/reviews/R0.draft.md", "look: Verde differs in the header\n")

    def test_a_release_with_design_needs_look_and_tag_needs_why(self):
        self.designed_release()
        code, _, err = self.mm("review", "R0", "HEALTHY", "--sha", self.head())
        self.assertEqual(code, 1)
        self.assertIn("--look <n>", err)
        self.assertIn("a slice's look difference is a REWORK",
                      self.mm("review", "01-cart", "PASS", "--sha", self.head(), "--look", "1")[2])
        code, _, err = self.mm("review", "R0", "HEALTHY", "--sha", self.head(), "--look", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("LOOK: 1\n", self.read(".mismagent/reviews/R0-1.md"))
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("names 1 artboard pair(s) that differ", err)
        code, _, err = self.mm("tag", "R0", "--why", "the header is fine as rendered")
        self.assertEqual(code, 0, err)
        self.assertIn("(HEALTHY, 1 look pair(s) differ)", self.read(".mismagent/decisions/0001-confirm-R0.md"))

    def test_no_look_difference_tags_without_why(self):
        self.designed_release()
        self.assertEqual(self.mm("review", "R0", "HEALTHY", "--sha", self.head(), "--look", "0")[0], 0)
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.isdir(os.path.join(self.dir, ".mismagent/decisions")))

class Spec(Repo):
    """`mm spec`: the human's commit beside a build — the spec paths only, in an index of its own."""

    def spec(self, note, **kw):
        code, out, err = self.mm("spec", note, **kw)
        return code, out + err

    def beside_bad(self):
        """sh: a builder's commit of a todo slice that does not parse."""
        git = shutil.which("git")
        return ('mkdir -p .mismagent/slices/todo && printf "# Slice\\n\\nKind: cleanup\\nRelease: R0\\n" > '
                '.mismagent/slices/todo/99-bad.md && env -u GIT_INDEX_FILE "%s" add .mismagent/slices/todo/99-bad.md '
                '&& env -u GIT_INDEX_FILE "%s" commit -q -m "99: beside"' % (git, git))

    def test_spec_checks_the_head_it_commits_on(self):
        self.write(".mismagent/brief.md", "# Brief\n\nA cart.\n")
        first = 'if [ "$2" = "HEAD" ] && [ ! -e .git/injected ]; then : > .git/injected; %s; fi' % self.beside_bad()
        code, out = self.spec("R0: the brief", env=self.fake_git("rev-parse", first, once=False))
        self.assertEqual(code, 1, out)  # a commit as HEAD is first read: the check comes after, and sees it
        self.assertIn("the spec does not hold together", out)
        self.assertIn("99-bad.md: Kind 'cleanup'", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "99: beside")  # nothing of ours on top of it

    def test_spec_never_commits_on_a_head_it_did_not_check(self):
        self.write(".mismagent/brief.md", "# Brief\n\nA cart.\n")
        code, out = self.spec("R0: the brief", env=self.fake_git("read-tree", self.beside_bad()))
        self.assertEqual(code, 1, out)  # after the check, before the commit: built again on the HEAD that moved
        self.assertIn("the spec does not hold together", out)
        self.assertIn("99-bad.md: Kind 'cleanup'", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "99: beside")

    def test_spec_commits_the_spec_paths_only(self):
        self.write("src/cart.py", "x = 1\n")  # the builder's work, uncommitted
        self.write("src/more.py", "y = 1\n")
        self.git("add", "src/more.py")  # and staged
        self.write("src/more.py", "y = 2\n")  # then changed again: the staged blob must survive
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.write(".mismagent/releases/R1.md", "# R1\n\n## Open questions\nnone\n")
        self.slice("02-more", release="R1", examples="EX-4")
        self.write(".mismagent/decisions/0001-x.md", "# x\n\n## Evidence\n- the human\n")
        self.write(".mismagent/decisions/worker.log", "debris\n")
        code, out = self.spec("R1: EX-4, slice 02")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "specify R1: EX-4, slice 02")
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split()),
                         [".mismagent/decisions/0001-x.md", ".mismagent/examples/cart.md",
                          ".mismagent/releases/R1.md", ".mismagent/slices/todo/02-more.md"])
        self.assertEqual(sorted(self.git("status", "--porcelain").splitlines()),
                         ["?? .mismagent/decisions/worker.log", "?? src/cart.py", "AM src/more.py"])
        self.assertEqual(self.git("show", ":src/more.py"), "y = 1")

    def test_spec_is_the_humans_for_the_gate(self):
        base = self.commit("base")
        self.started()
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.assertEqual(self.check("--base", base)[0], 1)  # uncommitted: nobody's yet
        code, out = self.spec("R1: EX-4")  # the todo folder is empty now: a pathspec git cannot match
        self.assertEqual(code, 0, out)
        code, out, err = self.check("--base", base)
        self.assertEqual(code, 0, out + err)

    def test_spec_with_nothing_to_commit_says_so(self):
        self.write("src/cart.py", "x = 1\n")
        code, out = self.spec("R1: nothing")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to commit", out)
        self.assertEqual(self.git("log", "--format=%s").splitlines(), ["init"])
        self.write(".mismagent/releases/R1.md", "# R1\n")
        self.assertEqual(self.spec("  ")[0], 1)  # a note of nothing

    def test_spec_refuses_a_spec_that_does_not_hold_together(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q |\n")  # 6 columns
        self.write(".mismagent/slices/todo/02-more.md", "# Slice\n\nRelease: R1\nExamples: EX-9\n")  # no Kind, no EX-9
        head, before = self.head(), self.git("status", "--porcelain")
        code, out = self.spec("R1: half written")
        self.assertEqual(code, 1)
        self.assertIn("6 columns", out)
        self.assertIn("02-more.md: Kind", out)
        self.assertIn("EX-9 is not in", out)
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (head, before))  # nothing moved, nothing staged
        # an error elsewhere in the spec holds it too: the file it names need not be the one written
        self.write(".mismagent/examples/cart.md", EXAMPLES)
        self.write(".mismagent/slices/todo/02-more.md", "# Slice\n\nKind: feature\nRelease: R1\nExamples: EX-3\nAfter: 01\n")
        code, out = self.spec("R1: slice 02")
        self.assertEqual(code, 1)
        self.assertIn("After: '01' names no single slice", out)

    def test_spec_ignores_the_builders_errors(self):
        self.write("src/big.py", "x = 1\n" * 401)
        self.commit("01-cart: big")
        self.assertEqual(self.check()[0], 1)  # the code is red, not the spec
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\nnone\n")
        code, out = self.spec("R0: release file")
        self.assertEqual(code, 0, out)
        self.assertIn(".mismagent/releases/R0.md", self.git("show", "--name-only", "--format=", "HEAD"))

    def test_spec_commits_a_cut_slice(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 02")
        self.git("rm", "-q", ".mismagent/slices/todo/02-more.md")  # staged: gone from the tree and the index
        code, out = self.spec("R0: slice 02 cut")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("show", "--name-status", "--format=", "HEAD").split(),
                         ["D", ".mismagent/slices/todo/02-more.md"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_spec_takes_a_quoted_name_and_a_rename(self):
        self.write(".mismagent/examples/caff\u00e8.md", "| id | given | when | then | rule | req | release |\n"
                   "| EX-4 | a | b | c | R | Q | R1 |\n")
        self.git("mv", ".mismagent/examples/cart.md", ".mismagent/examples/basket.md")
        code, out = self.spec("R1: caff\u00e8, basket")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(self.git("-c", "core.quotePath=false", "ls-tree", "--name-only", "HEAD",
                                         ".mismagent/examples/").split()),
                         [".mismagent/examples/basket.md", ".mismagent/examples/caff\u00e8.md"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_spec_refuses_a_rename_across_the_spec_paths_and_a_staged_divergence(self):
        self.git("mv", ".mismagent/examples/cart.md", "cart.md")
        head, before = self.head(), self.git("status", "--porcelain")
        code, out = self.spec("R1: moved out")
        self.assertEqual(code, 1)
        self.assertIn("across the spec paths", out)
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (head, before))
        self.git("mv", "cart.md", ".mismagent/examples/cart.md")
        self.write(".mismagent/releases/R1.md", "# R1\nv1\n")
        self.git("add", ".mismagent/releases/R1.md")
        self.write(".mismagent/releases/R1.md", "# R1\nv2\n")
        code, out = self.spec("R1: release")
        self.assertEqual(code, 1)
        self.assertIn("staged with other content", out)
        self.assertEqual(self.git("show", ":.mismagent/releases/R1.md"), "# R1\nv1")

    @unittest.skipIf(not hasattr(os, "fork") or sys.platform.startswith("win"), "flock")
    def test_the_lock_is_held_for_a_process_life(self):
        lock, quick = os.path.join(self.dir, ".git/mismagent.lock"), dict(os.environ, MM_LOCK_WAIT="0.2")
        holder = subprocess.Popen([sys.executable, "-c", "import fcntl, os, sys, time; fd = os.open(sys.argv[1], "
                                   "os.O_CREAT | os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX); print('held', flush=True); "
                                   "time.sleep(30)", lock], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            self.write(".mismagent/releases/R1.md", "# R1\n")
            self.slice("02-more", release="R1", examples="EX-3")
            code, out = self.spec("R1: release", env=quick)
            self.assertEqual(code, 1)
            self.assertIn("another mm", out)
            self.assertEqual(self.git("log", "--format=%s").splitlines(), ["init"])
            code, _, err = self.mm("start", "02-more", env=quick)  # a state move waits for the lock too
            self.assertEqual(code, 1)
            self.assertIn("another mm", err)
            self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/todo/02-more.md")))
        finally:
            holder.kill()
            holder.wait()
        code, out = self.spec("R1: release, slice 02")  # the holder died: the lock went with it
        self.assertEqual(code, 0, out)

    def test_a_commit_beside_a_state_move_refuses_it_and_puts_the_file_back(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.write(".mismagent/slices/todo/02-more.md", self.read(".mismagent/slices/todo/02-more.md").replace("\n", "\r\n"))
        os.chmod(os.path.join(self.dir, ".mismagent/slices/todo/02-more.md"), 0o755)
        self.commit("specify R0: slice 02")
        with open(os.path.join(self.dir, ".mismagent/slices/todo/02-more.md"), "rb") as f:
            before = f.read()
        code, _, err = self.mm("start", "02-more", env=self.beside())
        self.assertEqual(code, 1)
        self.assertIn("HEAD moved", err)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "01-cart: beside")  # theirs stands, ours is not on it
        with open(os.path.join(self.dir, ".mismagent/slices/todo/02-more.md"), "rb") as f:
            self.assertEqual(f.read(), before)  # byte for byte, mode too
        self.assertTrue(os.stat(os.path.join(self.dir, ".mismagent/slices/todo/02-more.md")).st_mode & 0o100)
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/02-more.md")))
        self.assertEqual(self.git("status", "--porcelain"), "")
        code, _, err = self.mm("start", "02-more")  # run again: on the new HEAD
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("log", "--format=%s").splitlines()[:2], ["mm start 02-more", "01-cart: beside"])

    def test_spec_builds_again_on_a_head_that_moved(self):
        self.write(".mismagent/releases/R1.md", "# R1\n")
        code, out = self.spec("R1: release", env=self.beside("01-cart: green"))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "--format=%s").splitlines(), ["specify R1: release", "01-cart: green", "init"])
        self.write(".mismagent/releases/R1.md", "# R1\nmore\n")
        code, out = self.spec("R1: again", env=self.beside("01-cart: busy", once=False))
        self.assertEqual(code, 1)
        self.assertIn("kept moving", out)
        self.assertEqual(self.git("status", "--porcelain").split(), ["M", ".mismagent/releases/R1.md"])  # still ours to commit

    def test_a_published_commit_stands_when_the_index_cannot_follow(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 02")
        code, _, err = self.mm("start", "02-more", env=self.fake_git("reset", "exit 128"))  # once: the retry follows
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.slice("03-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 03")
        self.assertEqual(self.mm("park", "02-more")[0], 0)
        code, _, err = self.mm("start", "03-more", env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.assertIn("published as", err)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "mm start 03-more")  # the commit stands
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/03-more.md")))  # not put back
        self.git("reset", "-q", "--", ".mismagent/slices")  # by hand, as the message says
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_tag_finishes_after_its_review_commit_stood_alone(self):
        self.done_release("R0")
        self.review("R0-1", "HEALTHY")
        code, _, err = self.mm("tag", "R0", env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.assertIn("published as", err)
        self.assertEqual((self.git("tag", "-l"), self.git("log", "-1", "--format=%s")), ("", "review: R0"))
        code, _, err = self.mm("tag", "R0")  # the index healed under the lock; the review read through its own commit
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("log", "-1", "--format=%s", "R0"), "review: R0")  # the same commit, tagged
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_a_cut_reconciliation_heals_at_the_next_move(self):
        self.slice("01-cart")
        self.acceptance("test_01-cart.py", "# EX-1\n")
        self.commit("plan")
        killed = self.fake_git("reset", 'kill -KILL "$PPID"; exit 128')  # mm dies as its ref has just moved
        self.assertNotEqual(self.mm("start", "01-cart", env=killed)[0], 0)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "mm start 01-cart")  # the commit stands
        self.assertNotEqual(self.git("status", "--porcelain"), "")  # the index as before it
        code, _, err = self.mm("park", "01-cart")  # the record names what that publish left
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".git", "mismagent.cut")))

    def test_an_index_nobody_recorded_is_nobodys_leftover(self):
        self.started()
        self.write(".mismagent/decisions/0001-human.md", "# a choice\n\n## Evidence\n- the human\n")
        self.commit("specify R0: a choice")
        self.write(".mismagent/decisions/0001-human.md", "# another\n\n## Evidence\n- the human\n")
        self.git("add", ".mismagent/decisions/0001-human.md")  # staged by someone, the tree back as at HEAD:
        self.write(".mismagent/decisions/0001-human.md", "# a choice\n\n## Evidence\n- the human\n")
        before = self.git("ls-files", "-s")  # what a cut publish would look like, and mm published nothing
        self.assertEqual(self.mm("designed", "R0: nothing")[0], 0)  # a move under the lock
        self.assertEqual(self.git("ls-files", "-s"), before)

    def test_land_takes_review_names_literally_and_records_a_review_deleted(self):
        self.started()
        self.work()
        self.write(".mismagent/reviews/old-evidence.md", "old\n")
        self.commit("review: old evidence")  # a review's own commit: read through
        self.review("01-cart-1", "PASS")
        os.remove(os.path.join(self.dir, ".mismagent/reviews/old-evidence.md"))
        self.write(".mismagent/reviews/*.md", "a name, not a pattern\n")
        self.write(".mismagent/reviews/unfinished.draft.md", "draft\n")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        shown = self.git("-c", "core.quotePath=false", "show", "--name-status", "--format=", "HEAD")
        self.assertIn("D\t.mismagent/reviews/old-evidence.md", shown)
        self.assertIn("A\t.mismagent/reviews/*.md", shown)
        self.assertNotIn("draft", shown)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_the_recovery_command_quotes_a_path(self):
        self.write(".mismagent/decisions/one choice.md", "# one\n\n## Evidence\n- the human\n")
        code, out = self.spec("R0: a choice", env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.assertIn("git reset -- '.mismagent/decisions/one choice.md'", out)

    def test_land_commits_the_review_files_one_by_one_and_keeps_a_draft_until_then(self):
        self.started()
        self.work()
        self.review("01-cart-1", "PASS")
        self.write(".mismagent/reviews/someone.draft.md", "unfinished\n")
        code, _, err = self.mm("land", "01-cart", env=self.beside("specify R0: beside"))  # refused: the draft stays
        self.assertEqual(code, 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/someone.draft.md")))
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        self.assertNotIn("draft", self.git("show", "--name-only", "--format=", "HEAD"))
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".mismagent/reviews/someone.draft.md")))

    def test_spec_reconciles_a_stale_index_without_an_empty_commit(self):
        self.write(".mismagent/releases/R1.md", "# R1\n")
        self.assertEqual(self.spec("R1: release")[0], 0)
        head = self.head()
        self.git("read-tree", "HEAD~1")  # the index as before the commit: a spec cut after its ref moved
        self.assertNotEqual(self.git("status", "--porcelain"), "")
        code, out = self.spec("R1: again")
        self.assertEqual(code, 0, out)
        self.assertIn("as committed", out)
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (head, ""))

    def test_a_specify_commit_that_moves_code_is_a_code_commit(self):
        self.started()
        self.work()
        self.review("01-cart-1", "PASS")
        self.assertEqual(self.next()["action"], "land")
        os.makedirs(os.path.join(self.dir, ".mismagent/decisions"), exist_ok=True)
        self.git("mv", "src/cart.py", ".mismagent/decisions/cart.py")
        self.commit("specify R0: moved by hand")  # a specify subject on code: not a spec commit
        self.assertNotEqual(self.next()["action"], "land")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("no PASS review of 01-cart at HEAD", err)

    def test_the_tree_names_specifys_files_among_others(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 02")
        self.write("src/cart.py", "x = 1\n")
        self.write(".mismagent/releases/R0.md", "# R0\n")
        code, _, err = self.mm("start", "02-more")
        self.assertEqual(code, 1)
        self.assertIn("among them specify's (.mismagent/releases/R0.md)", err)

    def test_wait_reports_the_minutes_since_the_last_write(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 02")
        self.write(".mismagent/releases/R0.md", "# R0\n")
        os.utime(os.path.join(self.dir, ".mismagent/releases/R0.md"), (time.time() - 7300, time.time() - 7300))
        d = self.next()
        self.assertEqual(d["action"], "wait")
        self.assertGreaterEqual(d["minutes"], 121)
        self.assertIn("min since its last write", d["reason"])

    def test_the_gate_names_specify_on_an_uncommitted_example(self):
        base = self.commit("base")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        code, out, _ = self.check("--base", base)
        self.assertEqual(code, 1)
        self.assertIn("specify is writing beside you", out)

    def test_a_spec_commit_keeps_a_review_at_head(self):
        self.started()
        self.work()
        read = self.head()  # the reviewer reads here
        self.write(".mismagent/releases/R0.md", "# R0\n\n## Open questions\nnone\n")
        self.assertEqual(self.spec("R0: release file")[0], 0)
        self.write(".mismagent/reviews/01-cart.draft.md", "# Review\nfine\n")
        code, _, err = self.mm("review", "01-cart", "PASS", "--sha", read[:9])  # HEAD moved by specify alone
        self.assertEqual(code, 0, err)
        self.write(".mismagent/examples/pay.md", "| id | given | when | then | rule | req | release |\n"
                   "| EX-4 | a | b | c | R | Q | R1 |\n")
        self.assertEqual(self.spec("R1: EX-4")[0], 0)
        self.assertEqual(self.next()["action"], "land")  # not resume: the PASS holds through specify's commits
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)

    def test_a_slice_added_beside_the_build_starts_in_its_turn(self):
        self.started()  # 01-cart in doing
        self.slice("02-more", release="R0", examples="EX-2")
        self.assertEqual(self.spec("R0: slice 02")[0], 0)
        self.assertEqual(self.next()["action"], "build")  # the slice in doing first
        self.work()
        self.review("01-cart-1", "PASS")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 0, err)
        d = self.next()
        self.assertEqual((d["action"], d["slice"]), ("start", "02-more"))

    def test_a_release_in_confirm_goes_back_to_the_build_when_a_slice_is_added(self):
        self.done_release("R0")
        self.review("R0-1", "HEALTHY")
        self.assertEqual(self.next()["action"], "confirm")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R0 |\n")
        self.slice("02-more", release="R0", examples="EX-4")
        self.assertEqual(self.spec("R0: EX-4, slice 02")[0], 0)
        d = self.next()
        self.assertEqual((d["action"], d["slice"]), ("start", "02-more"))

    def test_next_waits_while_specify_writes(self):
        self.slice("02-more", release="R0", examples="EX-2")
        self.commit("specify R0: slice 02")
        self.write(".mismagent/releases/R0.md", "# R0\n")  # being written, not committed
        d = self.next()
        self.assertEqual(d["action"], "wait")
        self.assertIn(".mismagent/releases/R0.md", d["reason"])
        code, _, err = self.mm("start", "02-more")
        self.assertEqual(code, 1)
        self.assertIn("specify is writing beside you", err)
        self.assertEqual(self.spec("R0: release file")[0], 0)
        self.assertEqual(self.next()["action"], "start")
        self.started()
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R0 |\n")
        self.assertEqual(self.next()["action"], "wait")
        self.write("src/cart.py", "x = 1\n")  # the builder's own dirt beside it: its work, resumed
        self.assertEqual(self.next()["action"], "resume")

    def test_built_names_specify_on_its_dirt(self):
        self.started()
        self.write("src/cart.py", "x = 1\n")
        self.commit("01-cart: code")
        self.write(".mismagent/releases/R0.md", "# R0\n")
        code, _, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 1)
        self.assertIn("specify is writing beside you (.mismagent/releases/R0.md)", err)
        self.assertEqual(self.spec("R0: release")[0], 0)
        self.assertEqual(self.mm("built", "01-cart", "--friction", "none")[0], 0)

    def test_land_checks_again_after_the_gate(self):
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: git commit -q --allow-empty -m '01-cart: during the gate'"))
        self.started()
        self.work()  # the gate commits once here too
        self.review("01-cart-1", "PASS")
        self.forget_gate()  # no run on record for this code tree: land's gate runs the suite
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("no PASS review of 01-cart at HEAD", err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/01-cart.md")))

    def test_tag_checks_again_after_the_gate(self):
        joins = ("mkdir -p .mismagent/slices/todo && printf 'Kind: feature\\nRelease: R0\\nExamples: EX-2\\n' "
                 "> .mismagent/slices/todo/02-more.md && git add .mismagent/slices/todo && "
                 "git commit -q -m 'specify R0: slice 02' -- .mismagent/slices/todo")
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: " + joins))
        self.done_release("R0")
        self.review("R0-1", "HEALTHY")
        code, _, err = self.mm("tag", "R0")
        self.assertEqual(code, 1)
        self.assertIn("slices not done: 02-more", err)
        self.assertEqual(self.git("tag", "-l"), "")


class Conventions(Repo):
    """`mm conventions`: the conventions session's commit beside a build — its paths only, the human's subject."""

    SKILL = ".claude/skills/conventions/SKILL.md"

    def conventions(self, note, *args, **kw):
        code, out, err = self.mm("conventions", note, *args, **kw)
        return code, out + err

    def test_conventions_commits_its_paths_only_and_is_the_humans_for_the_gate(self):
        base = self.commit("base")
        self.started()
        doing = ".mismagent/slices/doing/01-cart.md"
        self.write("src/cart.py", "x = 1\n")  # the builder's work, uncommitted
        self.write("src/more.py", "y = 1\n")
        self.git("add", "src/more.py")  # and staged
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n")
        self.write(".mismagent/decisions/0001-errors.md", "# errors\n\n## Evidence\n- the human\n")
        self.write("ARCHITECTURE.md", "# Architecture\n\nTyped errors.\n")
        self.write(doing, self.read(doing) + "\n## Question\nWhich errors?\n\n## Answer\nTyped.\n")
        self.write(".mismagent/decisions/0002-human.md", "# specify's, half written\n")  # another session's, beside
        self.assertEqual(self.check("--base", base)[0], 1)  # uncommitted: nobody's yet
        head = self.head()
        for bad, why in ((".mismagent/decisions", "is a folder"), (".claude/skills/conventions", "is a folder"),
                         ("src/cart.py", "not a file `mm conventions` commits by name"),
                         (".mismagent/slices/todo/01-cart.md", "not a file `mm conventions` commits by name")):
            code, out = self.conventions("errors: topic updated", bad)
            self.assertEqual((code, self.head()), (1, head), bad)
            self.assertIn(why, out)
        code, out = self.conventions("errors:  topic updated", ".mismagent/decisions/0001-errors.md", "ARCHITECTURE.md")
        self.assertEqual(code, 0, out)
        self.assertIn("conventions errors: topic updated: 4 file(s)", out)
        self.assertIn("left as they are, not named: .mismagent/decisions/0002-human.md", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "conventions errors: topic updated")
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split()),
                         [self.SKILL, ".mismagent/conventions-proposals.md", ".mismagent/decisions/0001-errors.md",
                          "ARCHITECTURE.md"])
        os.remove(os.path.join(self.dir, ".mismagent/decisions/0002-human.md"))
        self.assertEqual(sorted(self.git("status", "--porcelain").splitlines()),  # the helper strips the first line
                         ["?? src/cart.py", "A  src/more.py", "M " + doing])  # the rest as it was, staged or not
        code, out, err = self.check("--base", base)
        self.assertEqual(code, 0, out + err)  # the skill changed since Base, by the human
        code, out = self.conventions("errors: the builder's doubt answered", "--slice", "01")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), doing)
        self.assertEqual(sorted(self.git("status", "--porcelain").splitlines()), ["?? src/cart.py", "A  src/more.py"])
        head = self.head()
        code, out = self.conventions("errors: nothing more")
        self.assertEqual((code, self.head()), (0, head))
        self.assertIn("nothing to commit", out)
        self.assertEqual(self.conventions(" ")[0], 1)  # a note of nothing
        self.assertEqual(self.conventions("errors", "--slice", "09")[0], 1)  # no such slice

    def test_a_conventions_commit_typed_by_hand_is_the_humans_in_either_case(self):
        base = self.commit("base")
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        self.commit("Conventions: errors topic updated")
        code, out, err = self.check("--base", base)
        self.assertEqual(code, 0, out + err)
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit("Specify R1: EX-4")
        self.assertEqual(self.check("--base", base)[0], 0)
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are strings.\n")
        self.commit("Conventions-fix: errors")  # a lookalike is nobody's, capitalised or not
        self.assertEqual(self.check("--base", base)[0], 1)

    def test_conventions_is_held_by_a_broken_skill_never_by_the_code(self):
        self.write("src/big.py", "x = 1\n" * 401)
        self.commit("01-cart: big")
        self.assertEqual(self.check()[0], 1)  # the code is red, not the skill
        topic = ".claude/skills/conventions/references/practices/doubts.md"
        self.write(topic, "# doubts\n\n## Must\n- ask\n")
        head, before = self.head(), self.git("status", "--porcelain")
        code, out = self.conventions("doubts: created")
        self.assertEqual(code, 1)
        self.assertIn("the conventions do not hold together", out)
        self.assertIn("practices/doubts.md: no ## Never", out)
        self.assertNotIn("big.py", out)
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (head, before))  # nothing moved, nothing staged
        self.write(topic, "# doubts\n\n## Must\n- ask\n## Never\n- guess\n")
        code, out = self.conventions("doubts: created")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_conventions_builds_again_on_a_head_that_moved(self):
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        code, out = self.conventions("errors: topic updated", env=self.beside("01-cart: green"))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "--format=%s").splitlines(),
                         ["conventions errors: topic updated", "01-cart: green", "init"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_a_named_file_is_the_one_named_never_its_target_or_its_folder(self):
        self.write(".mismagent/decisions/old/a.md", "# a\n\n## Evidence\n- x\n")
        self.write(".mismagent/decisions/old/b.md", "# b\n\n## Evidence\n- x\n")
        self.commit("decisions")
        self.write(".mismagent/decisions/human.md", "# specify's, half written\n")
        os.symlink("human.md", os.path.join(self.dir, ".mismagent/decisions/mine.md"))
        code, out, err = self.mm("designed", "R0: my link", ".mismagent/decisions/mine.md")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), ".mismagent/decisions/mine.md")
        self.assertIn("left as they are, not named: .mismagent/decisions/human.md", out)
        shutil.rmtree(os.path.join(self.dir, ".mismagent/decisions/old"))  # two files deleted: the folder names neither
        head = self.head()
        code, _, err = self.mm("designed", "R0: deleted a", ".mismagent/decisions/old")
        self.assertEqual((code, self.head()), (1, head))
        self.assertIn("is a folder: name the files you wrote or deleted in it", err)
        code, out, err = self.mm("designed", "R0: deleted a", ".mismagent/decisions/old/a.md")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), ".mismagent/decisions/old/a.md")
        self.assertIn(".mismagent/decisions/old/b.md", out)  # left: deleted by someone, named by nobody
        self.write(".mismagent/decisions/own.log", "notes\n")
        head = self.head()
        code, _, err = self.mm("designed", "R0: a log", ".mismagent/decisions/own.log")
        self.assertEqual((code, self.head()), (1, head))  # never dropped in silence
        self.assertIn("own.log: run debris by its name: mm never commits it", err)
        os.remove(os.path.join(self.dir, ".mismagent/decisions/own.log"))
        self.write(".mismagent/design-notes.md", "- one note\n")
        code, out, err = self.mm("designed", "R0: notes", ".mismagent/design-notes.md",  # its own: named or not
                                 ".mismagent/conventions-proposals.md")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), ".mismagent/design-notes.md")

    def test_a_named_slice_refers_to_what_is_committed_or_in_its_commit(self):
        self.slice("05-old", examples="EX-1")
        self.commit("specify R0: slice 05")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R0 |\n")  # specify, writing
        self.slice("06-new", examples="EX-4")
        head = self.head()
        code, _, err = self.mm("designed", "R0: one slice", ".mismagent/slices/todo/06-new.md")
        self.assertEqual((code, self.head()), (1, head))
        self.assertIn("06-new.md: example EX-4 has no row in a committed example file", err)
        self.slice("05-old", examples="EX-1, EX-4")  # a slice there already, now naming the draft: the same
        code, _, err = self.mm("designed", "R0: one slice", ".mismagent/slices/todo/05-old.md")
        self.assertEqual((code, self.head()), (1, head))
        self.assertIn("05-old.md: example EX-4 has no row", err)
        self.slice("06-new", examples="EX-2")  # a committed example: specify's draft beside it holds nothing
        code, out, err = self.mm("designed", "R0: one slice", ".mismagent/slices/todo/06-new.md")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), ".mismagent/slices/todo/06-new.md")
        self.slice("07-mine", kind="refactor", examples="", extra="")
        path = ".mismagent/slices/todo/07-mine.md"
        self.write(path, self.read(path).replace("Examples:", "After: 08\nExamples:"))
        self.slice("08-human", kind="refactor", examples="")  # another session's draft, uncommitted
        head = self.head()
        code, _, err = self.mm("designed", "R0: after", path)
        self.assertEqual((code, self.head()), (1, head))
        self.assertIn("07-mine.md: After: '08' names no single committed slice", err)
        code, _, err = self.mm("designed", "R0: after", path, ".mismagent/slices/todo/08-human.md")  # both its own
        self.assertEqual(code, 0, err)
        self.assertEqual(self.mm("spec", "R0: EX-4")[0], 0)  # specify's own commit takes its examples, as ever
        self.assertEqual(self.check()[0], 0)

    def test_a_named_slices_references_are_read_in_the_commit_not_in_a_draft(self):
        self.write(".mismagent/examples/cart.md", EXAMPLES + "\nDraft idea: EX-4 will cover refunds.\n")
        self.slice("06-a", kind="refactor", examples="")
        self.slice("06-b", kind="refactor", examples="")
        self.commit("specify R0: a note, two slices")
        self.write(".mismagent/examples/cart.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R0 |\n")  # the row: a draft
        self.slice("05-mine", examples="EX-4")
        mine, head = ".mismagent/slices/todo/05-mine.md", self.head()
        code, _, err = self.mm("designed", "R0: one slice", mine)
        self.assertEqual((code, self.head()), (1, head))  # a mention in prose is no example
        self.assertIn("05-mine.md: example EX-4 has no row in a committed example file", err)
        self.write(".mismagent/examples/cart.md", EXAMPLES.replace("| EX-1 | a cart | add | 1 item | R | Q1 | R0 |\n", ""))
        self.slice("05-mine", examples="EX-1")  # committed; deleted only in specify's draft: still there for us
        self.write(mine, self.read(mine).replace("Examples:", "After: 06\nExamples:"))
        os.remove(os.path.join(self.dir, ".mismagent/slices/todo/06-b.md"))  # and one of two 06, deleted in a draft
        code, _, err = self.mm("designed", "R0: one slice", mine)
        self.assertEqual((code, self.head()), (1, head))
        self.assertIn("05-mine.md: After: '06' names no single committed slice", err)
        self.assertNotIn("EX-1", err)
        self.write(".mismagent/examples/notes.txt", "| EX-9 | x | y | z | R | Q | R0 |\n")  # no example file
        self.write(".mismagent/slices/archive/07-old.md", slice_text(kind="refactor", examples=""))  # no slice
        self.write(".mismagent/slices/todo/05-other.md", slice_text(kind="refactor", examples=""))
        self.git("add", ".mismagent/examples/notes.txt", ".mismagent/slices/archive", ".mismagent/slices/todo/05-other.md")
        self.git("commit", "-q", "-m", "specify R0: notes")
        head = self.head()
        for after, examples in (("05", "EX-1"), ("07-old", "EX-1"), ("06-a", "EX-9")):  # as the gate reads them:
            self.slice("05-mine", examples=examples)  # two slices numbered 05, itself one; a folder and a file it skips
            self.write(mine, self.read(mine).replace("Examples:", "After: %s\nExamples:" % after))
            code, _, err = self.mm("designed", "R0: one slice", mine)
            self.assertEqual((code, self.head()), (1, head), (after, examples))
            self.assertIn("EX-9 has no row" if examples == "EX-9" else "After: %r names no single committed slice" % after, err)
        self.slice("05-mine", examples="EX-1")
        self.write(mine, self.read(mine).replace("Examples:", "After: 06-a\nExamples:"))
        code, out, err = self.mm("designed", "R0: one slice", mine)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), mine)
        self.git("checkout", "-q", "--", ".mismagent/examples/cart.md", ".mismagent/slices/todo/06-b.md")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)  # what was committed holds together once the drafts are gone

    def test_a_staged_skill_or_map_is_nobodys_leftover(self):
        self.write(self.SKILL, "---\nname: conventions\n---\nStaged.\n")
        self.write("ARCHITECTURE.md", "# Architecture\n\nStaged.\n")
        self.git("add", self.SKILL, "ARCHITECTURE.md")
        self.write(self.SKILL, "---\nname: conventions\n---\n")  # the tree back as at HEAD, the staged version kept
        self.write("ARCHITECTURE.md", "# Architecture\n")
        staged = self.git("diff", "--cached", "--stat")
        self.assertIn("2 files changed", staged)
        for move in (("spec", "nothing"), ("designed", "R0: nothing"), ("spec", "again")):
            self.assertEqual(self.mm(*move)[0], 0, move)
            self.assertEqual(self.git("diff", "--cached", "--stat"), staged, move)  # whoever staged it still has it

    def test_a_cut_conventions_commit_heals_at_the_next_move(self):
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        self.write("ARCHITECTURE.md", "# Architecture\n\nTyped errors.\n")
        code, out = self.conventions("errors: topic updated", "ARCHITECTURE.md",
                                     env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.assertIn("published as", out)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "conventions errors: topic updated")  # the commit stands
        self.assertNotEqual(self.git("status", "--porcelain"), "")  # the index still at the skill and the map before it
        failing = self.fake_git("reset", "exit 128", once=False)
        self.assertEqual(self.mm("spec", "nothing", env=failing)[0], 0)  # the heal cannot reset either: it stays on record
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".git", "mismagent.cut")))
        self.assertEqual(self.mm("spec", "nothing")[0], 0)  # any move under the lock: the cut publish named its entries
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".git", "mismagent.cut")))

    def cut(self):
        """A conventions commit whose index could not follow: -> (the skill's blob before it, at it)."""
        old = self.git("rev-parse", "HEAD:" + self.SKILL)
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        code, out = self.conventions("errors: topic updated", env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.assertIn("published as", out)
        return old, self.git("rev-parse", "HEAD:" + self.SKILL)

    def record(self):
        return os.path.join(self.dir, ".git", "mismagent.cut")

    def test_a_merges_conflict_stages_are_never_mms_leftover(self):
        old, new = self.cut()
        stages = "".join("100644 %s %d\t%s\n" % (blob, n, self.SKILL) for n, blob in ((1, old), (2, new), (3, old)))
        subprocess.run(["git", "update-index", "--index-info"], cwd=self.dir, check=True, text=True,
                       input="0 %s\t%s\n" % ("0" * 40, self.SKILL) + stages)  # theirs is the blob that publish found
        before = self.git("ls-files", "-s", "--", self.SKILL)
        self.assertEqual(before.count("\n"), 2)
        self.assertEqual(self.mm("designed", "R0: nothing")[0], 0)  # a move under the lock
        self.assertEqual(self.git("ls-files", "-s", "--", self.SKILL), before)  # three stages, as the merge left them

    def test_a_record_mm_cannot_read_or_place_is_kept_and_said(self):
        self.cut()
        with open(self.record(), encoding="utf-8") as f:
            good = f.read()
        for failed in ("exit 128", "kill -TERM $$"):  # git's error, or its death, is no answer: kept
            self.assertEqual(self.mm("spec", "nothing", env=self.fake_git("merge-base", failed, once=False))[0], 0)
            with open(self.record(), encoding="utf-8") as f:
                self.assertEqual(f.read(), good, failed)
        for bad in ("", "{}\n", '{"commit": 1, "entries": []}\n', good[:len(good) // 2]):
            with open(self.record(), "w", encoding="utf-8") as f:
                f.write(bad or "not json\n")
            code, out, err = self.mm("spec", "nothing")
            self.assertEqual(code, 1)
            self.assertIn(".git/mismagent.cut: cannot be read", err)
            self.assertNotIn("Traceback", err)
            self.assertTrue(os.path.exists(self.record()))  # the only trace: the human looks, then removes it
        with open(self.record(), "w", encoding="utf-8") as f:
            f.write(good)
        self.assertEqual(self.mm("spec", "nothing")[0], 0)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(os.path.exists(self.record()))

    def test_a_record_that_cannot_be_written_commits_nothing(self):
        self.slice("01-cart")
        self.acceptance("test_01-cart.py", "# EX-1\n")
        head = self.commit("plan")
        code, _, err = self.mm("start", "01-cart", env=self.fake_git("commit-tree", "mkdir -p .git/mismagent.cut.new"))
        self.assertEqual(code, 1)
        self.assertIn(".git/mismagent.cut: cannot be written", err)
        self.assertNotIn("Traceback", err)
        os.rmdir(self.record() + ".new")
        self.assertEqual((self.head(), self.git("status", "--porcelain")), (head, ""))  # the move put back
        code, _, err = self.mm("start", "01-cart")
        self.assertEqual(code, 0, err)

    def test_a_version_staged_after_a_cut_commit_is_its_stagers(self):
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")
        code, out = self.conventions("errors: topic updated", env=self.fake_git("reset", "exit 128", once=False))
        self.assertEqual(code, 1)
        self.write(self.SKILL, "---\nname: conventions\n---\nOTHER STAGED\n")  # someone's next version, staged
        self.git("add", self.SKILL)
        self.write(self.SKILL, "---\nname: conventions\n---\nErrors are typed.\n")  # the tree back as at HEAD
        staged = self.git("diff", "--cached")
        self.assertIn("OTHER STAGED", staged)
        self.assertEqual(self.mm("spec", "nothing")[0], 0)
        self.assertEqual(self.git("diff", "--cached"), staged)  # not the entry that publish found: not mm's
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".git", "mismagent.cut")))


class Base(Repo):
    """A doing slice's `Base:` is where everything the gate compares starts: mm's alone."""

    PATH = ".mismagent/slices/doing/01-cart.md"

    def test_a_base_rewritten_by_hand_is_an_error(self):
        self.started()
        base = self.git("rev-parse", "HEAD~1")
        self.assertEqual(self.check()[0], 0)
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- max_file_lines: 1000"))
        loosened = self.commit("01-cart: settings")
        self.write(self.PATH, self.read(self.PATH).replace("Base: " + base, "Base: " + loosened))  # the gate moved with it
        self.write("src/cart.py", "x = 1\n" * 401)
        self.commit("01-cart: implementation")
        code, out, _ = self.check("--base", loosened)
        self.assertEqual(code, 1)
        self.assertIn("error: %s: Base: %s is not the one it was started with (%s, in %s): the Base is mm's"
                      % (self.PATH, loosened[:12], base[:12], self.git("rev-parse", "HEAD~2")[:7]), out)
        code, _, err = self.mm("built", "01-cart", "--friction", "none")
        self.assertEqual(code, 1)  # the builder's own gate is red on it
        self.assertNotIn("Built:", self.read(self.PATH))
        self.write(self.PATH, self.read(self.PATH).replace("Base: " + loosened, "Base: " + base[:12]))  # the same commit
        self.commit("01-cart: base back")
        code, out, err = self.check("--base", base)
        self.assertEqual(code, 0, out + err)
        self.assertIn("`max_file_lines:` changed since %s (was 400, now 1000)" % base, out)  # and the loosening shows

    def test_a_base_edited_and_not_committed_is_an_error_too(self):
        self.started()
        base = self.git("rev-parse", "HEAD~1")
        self.write(self.PATH, self.read(self.PATH).replace("Base: " + base, "Base: " + self.head()))
        self.assertEqual(self.check()[0], 1)
        self.write(self.PATH, self.read(self.PATH).replace("Base: " + self.head(), "Base: " + base)
                   + "Base: " + self.head() + "\n")  # a second line: the last one is read
        self.assertEqual(self.check()[0], 0)  # after ## Goal: not a header
        self.write(self.PATH, self.read(self.PATH).replace("Base: " + base, "Base: %s\nBase: %s" % (base, self.head()), 1))
        code, out, _ = self.check()  # a second header line: the last one is the one read
        self.assertEqual(code, 1)
        self.assertIn("is not the one it was started with (%s" % base[:12], out)

    def test_a_slice_deleted_and_added_again_is_no_new_start(self):
        self.started()
        base, text = self.git("rev-parse", "HEAD~1"), self.read(self.PATH)
        os.remove(os.path.join(self.dir, self.PATH))
        self.commit("01: reorganize notes")
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400", "- max_file_lines: 1000"))
        loosened = self.commit("01: settings")
        self.write(self.PATH, text.replace("Base: " + base, "Base: " + loosened))
        self.write("src/cart.py", "x = 1\n" * 401)
        self.commit("01: restored notes and implementation")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("Base: %s is not the one it was started with (%s" % (loosened[:12], base[:12]), out)
        self.assertEqual(self.mm("built", "01-cart", "--friction", "none")[0], 1)

    def test_a_start_commit_carried_elsewhere_keeps_its_base(self):
        self.started()
        start, base = self.head(), self.git("rev-parse", "HEAD~1")
        self.git("checkout", "-q", "-b", "newbase", base)
        self.commit("specify another note")  # an empty commit beside: the same code
        self.git("cherry-pick", start)
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)  # the header is what it was: nothing to say
        self.assertIn("Base: " + base, self.read(self.PATH))

    def test_a_slice_parked_and_started_again_has_its_new_base(self):
        self.started()
        self.assertEqual(self.mm("park", "01-cart")[0], 0)
        self.commit("specify R0: a note")
        code, _, err = self.mm("start", "01-cart")
        self.assertEqual(code, 0, err)
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Base: " + self.git("rev-parse", "HEAD~1"), self.read(self.PATH))


if __name__ == "__main__":
    unittest.main()
