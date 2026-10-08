"""Tests for tools/mm.py — stdlib unittest; each test runs mm in a temporary git repository.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -p 'test_mm.py' -v"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

MM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mm.py")

CLAUDE = "# Project\n\n## mismagent\n- test: true\n-   lint :  `true`\n- max_file_lines: 400\n\n## Other\n- test: false\n"
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


class Repo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mm-test-")
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.write("CLAUDE.md", CLAUDE)
        self.write(".mismagent/examples.md", EXAMPLES)
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

    def mm(self, *args, cwd=None):
        p = subprocess.run([sys.executable, MM, *args], cwd=cwd or self.dir, capture_output=True,
                           text=True)
        return p.returncode, p.stdout, p.stderr

    def next(self):
        code, out, err = self.mm("next", "--json")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def slice(self, name, state="todo", **kw):
        self.write(".mismagent/slices/%s/%s.md" % (state, name), slice_text(**kw))

    def review(self, name, verdict, sha=None, scores="simple=4 naming=-"):
        self.write(".mismagent/reviews/%s.md" % name,
                   "# Review\nVERDICT: %s\nSHA: %s\nSCORES: %s\n" % (verdict, (sha or self.head())[:9], scores))

    def work(self, stem="01-cart", code="x = 1\n", msg="code"):
        """Builder work: code plus the progress entry, committed."""
        self.write("src/cart.py", code)
        self.write(".mismagent/progress.md", "# Progress\n\n## %s — done\nbuilt it\n" % stem)
        return self.commit(msg)

    def acceptance(self, rel, text):
        self.write("tests/acceptance/" + rel, text)

    def started(self, name="01-cart", **kw):
        """A slice in doing via mm start."""
        self.slice(name, **kw)
        self.commit("plan")
        code, _, err = self.mm("start", name)
        self.assertEqual(code, 0, err)

    def done_release(self, release="R0"):
        """All slices of a release done (with acceptance markers), committed."""
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(release=release, examples="EX-1").replace("Examples", "Base: abc1234\nExamples"))
        self.acceptance("test_cart.py", "def test_ex1():  # EX-1\n    pass\n")
        self.commit("done")

    def check(self, *args):
        return self.mm("check", *args)


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
        self.write(".mismagent/examples.md", EXAMPLES +
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
        for sub in ("status", "next", "start", "land", "gate", "tag", "check"):
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
        self.assertIn("progress.md", d["reason"])
        self.write(".mismagent/progress.md", "## 01-cart\nok\n")
        self.commit("progress")
        self.assertEqual(self.next()["action"], "review")
        code, out, _ = self.mm("next")
        self.assertTrue(out.startswith("review 01-cart — "), out)

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

    def test_design_pass_then_confirm_after_two(self):
        self.done_release()
        self.review("R0-1", "DESIGN-PASS")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("design-pass", "R0"))
        self.commit("pass 1")
        self.review("R0-2", "DESIGN-PASS")
        self.assertEqual(self.next()["action"], "design-pass")
        self.commit("pass 2")
        self.review("R0-3", "DESIGN-PASS")
        d = self.next()
        self.assertEqual((d["action"], d["release"]), ("confirm", "R0"))
        self.assertIn("2 design passes", d["reason"])

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

    def test_five_notes_do_not_trigger(self):
        self.write(".mismagent/design-notes.md", "".join("- note %d\n" % i for i in range(5)))
        self.slice("01-cart")
        self.assertEqual(self.next()["action"], "start")

    def test_start_order(self):
        self.slice("03-b")
        self.slice("02-a")
        self.assertEqual(self.next()["slice"], "02-a")
        self.slice("07-r", kind="refactor", examples="")
        self.assertEqual(self.next()["slice"], "07-r")

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

    def test_conventions_after_a_slice_with_proposals(self):
        self.done_release()
        self.slice("02-more", examples="EX-2")
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n\n- create errors: typed errors (`src/cart.py`)\n")
        self.commit()
        d = self.next()
        self.assertEqual(d["action"], "conventions")
        self.assertEqual(d["proposals"], 1)
        self.write(".mismagent/conventions-proposals.md", "# Proposals\n")
        self.commit()
        self.assertNotEqual(self.next()["action"], "conventions")

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
        self.assertEqual(d["action"], "conventions")
        self.assertIn("no conventions skill", d["reason"])

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

    def test_low_score_demotes_pass(self):
        self.started()
        self.work()
        self.review("01-cart-1", "PASS", scores="simple=4 naming=3 errors=-")
        d = self.next()
        self.assertEqual((d["action"], d["k"]), ("rework", 1))
        self.assertIn("naming=3 < 4 counts as REWORK", d["reason"])
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("naming=3", err)

    def test_low_score_demotes_healthy(self):
        self.done_release()
        self.review("R0-1", "HEALTHY", scores="simple=5 layering=2")
        d = self.next()
        self.assertEqual(d["action"], "design-pass")
        self.assertIn("counts as DESIGN-PASS", d["reason"])

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
        self.review("01-cart-4", "PASS", scores="")
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
        self.work()
        self.review("01-cart-1", "PASS")
        code, _, err = self.mm("land", "01-cart")
        self.assertEqual(code, 1)
        self.assertIn("EX-1 has no acceptance marker under tests/acceptance/", err)
        self.assertTrue(os.path.exists(os.path.join(self.dir, ".mismagent/slices/doing/01-cart.md")))

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
        self.assertIn("gate: green", out)

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

    def test_gate_red_on_missing_config_or_check(self):
        self.write("CLAUDE.md", "# nothing\n")
        self.assertEqual(self.mm("gate")[0], 1)
        self.write("CLAUDE.md", CLAUDE)
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-1 | dup | x | y | R | Q | R0 |\n")
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

    def test_tag_refuses_red_gate(self):
        self.done_release()
        self.write("CLAUDE.md", CLAUDE.replace("- test: true", "- test: false"))
        self.commit()
        self.assertEqual(self.mm("tag", "R0")[0], 1)
        self.assertEqual(self.git("tag", "-l"), "")


class Check(Repo):
    def assertError(self, fragment, *args):
        code, out, err = self.check(*args)
        self.assertEqual(code, 1, out)
        self.assertIn(fragment, out)
        self.assertTrue(err.strip())

    def test_ok(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_malformed_examples(self):
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-4 | x | y | z | R | Q |\n")
        self.assertError("6 columns")
        self.write(".mismagent/examples.md", EXAMPLES + "| E-4 | x | y | z | R | Q | R0 |\n")
        self.assertError("is not EX-<n>")
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-4 | x | y | z | R | Q |  |\n")
        self.assertError("no release")

    def test_duplicate_ids(self):
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-2 | x | y | z | R | Q | R1 |\n")
        self.assertError("duplicate id EX-2")

    def test_bad_slice_headers(self):
        self.slice("01-cart", kind="epic")
        self.assertError("Kind 'epic'")
        self.slice("01-cart", examples="EX-7")
        self.assertError("EX-7 is not in examples.md")
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
        self.write(".mismagent/examples.md",
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
        self.work()
        self.assertEqual(self.check()[0], 0)  # while building: no marker required yet
        self.assertError("01-cart.md: doing, but EX-1 has no acceptance marker", "--base", base)
        self.acceptance("test_cart.py", "# EX-1\n")
        self.commit("acc")
        self.assertEqual(self.check("--base", base)[0], 0)

    def test_acceptance_folders_from_claude_md(self):
        self.write("CLAUDE.md", CLAUDE.replace("- max_file_lines: 400",
                                               "- max_file_lines: 400\n- acceptance: app/src/acc, web/acc/"))
        self.write(".mismagent/slices/done/01-cart.md",
                   slice_text(examples="EX-1, EX-2").replace("Examples", "Base: abc1234\nExamples"))
        self.write("app/src/acc/CartTest.kt", "// EX-1\n")
        self.write("tests/acceptance/test_cart.py", "# EX-2\n")  # not a configured folder
        self.commit()
        self.assertError("EX-2 has no acceptance marker under app/src/acc, web/acc/")
        self.write("web/acc/cart.test.js", "// EX-2\n")
        self.commit()
        self.assertEqual(self.check()[0], 0)

    def test_long_convention_topic_warns(self):
        self.write(".claude/skills/conventions/references/tests.md", "word " * 301)
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("references/tests.md: 301 words > 300", out)
        self.write(".claude/skills/conventions/references/tests.md", "word " * 300)
        self.assertNotIn("words >", self.check()[1])

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

    def test_base_acceptance_modified(self):
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-4 | x | y | z (superseded by EX-3) | R | Q | R1 |\n")
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        self.acceptance("test_old.py", "# EX-4\n")
        base = self.commit("acc")
        self.slice("02-more", state="doing", examples="EX-2")
        path = ".mismagent/slices/doing/02-more.md"
        self.write(path, self.read(path).replace("Examples", "Base: %s\nExamples" % base))
        self.acceptance("test_new.py", "# EX-2\n")
        self.commit("added")
        self.assertEqual(self.check("--base", base)[0], 0)
        self.acceptance("test_old.py", "# EX-4 dropped\n")  # a superseded example: allowed
        self.acceptance("test_other.py", "# EX-3 EX-2 shared\n" + "x = 1\n" * 20)  # names EX-2
        self.assertEqual(self.check("--base", base)[0], 0, self.check("--base", base)[1])
        self.acceptance("test_other.py", "# EX-3 weakened\n" + "x = 1\n" * 20)
        self.assertError("tests/acceptance/test_other.py: acceptance test modified", "--base", base)
        self.write(path, self.read(path).replace("Kind: feature", "Kind: refactor"))
        self.assertEqual(self.check("--base", base)[0], 0)  # refactor slices may modify them
        self.write(path, self.read(path).replace("Kind: refactor", "Kind: feature"))
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        self.git("mv", "tests/acceptance/test_other.py", "tests/acceptance/test_renamed.py")
        self.acceptance("test_renamed.py", "# EX-3\n" + "x = 1\n" * 19 + "x = 2\n")
        self.commit("rename and edit")
        self.assertError("tests/acceptance/test_renamed.py: acceptance test renamed and edited", "--base", base)

    def test_base_pure_rename_allowed(self):
        self.acceptance("test_other.py", "# EX-3\n" + "x = 1\n" * 20)
        base = self.commit("acc")
        self.started(name="02-more", examples="EX-2")
        self.git("mv", "tests/acceptance/test_other.py", "tests/acceptance/test_moved.py")
        self.acceptance("test_new.py", "# EX-2\n")
        self.commit("move")
        self.assertEqual(self.check("--base", base)[0], 0)

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
        self.write(".mismagent/examples.md", EXAMPLES + "| EX-4 | x | y | z | R | Q | R1 |\n")
        self.commit()
        self.assertError(".mismagent/examples.md: changed since", "--base", base)
        self.write(".mismagent/examples.md", EXAMPLES)
        self.write(".claude/skills/conventions/SKILL.md", "---\nname: conventions\n---\nmore\n")
        self.commit()
        self.assertError(".claude/skills/conventions/SKILL.md: changed since", "--base", base)

    def test_bad_base_ref(self):
        self.assertEqual(self.check("--base", "no-such-ref")[0], 1)

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
                   "Errors: `references/errors.md`. Model: `src/cart.py`, not `x.y`.\n")
        self.write(".claude/skills/conventions/references/errors.md",
                   "See `src/errors.py` and `tests/acceptance/`.\n")
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("cites src/errors.py", out)
        self.assertIn("cites tests/acceptance/", out)
        self.assertNotIn("cart.py", out)
        self.assertNotIn("references/errors.md,", out)
        self.write("src/errors.py", "y = 2\n")
        os.makedirs(os.path.join(self.dir, "tests/acceptance"), exist_ok=True)
        self.assertEqual(self.check()[0], 0)

if __name__ == "__main__":
    unittest.main()
