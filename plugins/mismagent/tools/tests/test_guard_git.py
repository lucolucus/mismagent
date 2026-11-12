"""Tests for hooks/guard-git.py — stdlib unittest; feeds a PreToolUse event on stdin.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_prompt_lint import mm_calls  # noqa: E402

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "hooks", "guard-git.py")


def run(command, agent="mismagent-builder", cwd=None):
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    if agent is not None:
        event["agent_type"] = agent
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True,
                         text=True, check=True).stdout.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


def decide(command, agent="mismagent-builder", cwd=None):
    out = run(command, agent, cwd)
    return out["permissionDecision"] if out else "allow"


GUARDED = ("mismagent-builder", "mismagent-reviewer", "mismagent-architect")


class GuardGit(unittest.TestCase):
    def test_plain_forbidden_commands_denied(self):
        for cmd in ("git merge feat", "git push origin x", "git rebase main",
                    "git reset --hard HEAD~1", "git checkout main", "git checkout -b x",
                    "git switch -c x", "git branch -d x", "git branch -D x",
                    "git branch --delete x", "git branch -fd x", "git stash", "git stash pop",
                    "git tag R1", "git tag -a v1 -m x",
                    "git mv .mismagent/slices/todo/S1.md .mismagent/slices/doing/",
                    "git mv /r/.mismagent/slices/S1.md /r/.mismagent/slices/done/S1.md"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_sweeps_of_the_humans_files_denied(self):
        for cmd in ("git clean -fd", "git clean -n", "git restore .", "git restore --staged src/a.py",
                    "git add -A", "git add --all", "git add .", "git add -u", "git add -fA src",
                    "git add :/", "git add *", "git commit -am wip", "git commit -a -m x",
                    "git commit --all -m x", "git commit -sam x"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_global_option_bypasses_denied(self):
        for cmd in ('git -C "/tmp/my repo" merge x', "git --no-pager push",
                    'git -c "user.name=Some Name" rebase x', "git --git-dir=/r/.git -P push",
                    "GIT_DIR=/r git --work-tree /w reset --hard", "git -C /r tag R1"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_later_segments_checked(self):
        for cmd in ("git status && git push", "true; git merge x", "ls | git rebase x",
                    "git diff\ngit push", "false || /usr/bin/git push", "git add -A; git stash"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_main_session_allowed(self):
        self.assertEqual(decide('git -C "/tmp/my repo" merge x', agent=None), "allow")
        self.assertEqual(decide("git push", agent=""), "allow")
        self.assertEqual(decide("git tag R1", agent=None), "allow")

    def test_normal_commands_allowed_for_builder(self):
        for cmd in ("git status", "git diff main...HEAD", "git log --oneline | head",
                    "git add src/a.py tests/test_a.py && git status", 'echo "git push" > notes.txt',
                    "git commit -m 'S1 green'", "git add -p src/a.py && git commit --amend -m wip",
                    "git add src/ && git commit -m 'adds under src'", "git commit -m '-a flag'",
                    "git reset --soft HEAD~1", "git mv src/a.py src/b.py", "git branch",
                    "git branch --show-current", "git show HEAD:.mismagent/slices/S1.md"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_all_three_agents_guarded(self):
        for agent in ("mismagent-builder", "mismagent-reviewer", "mismagent-architect"):
            self.assertEqual(decide("git merge x", agent=agent), "deny", agent)

    def test_namespaced_agent_denied(self):
        self.assertEqual(decide("git push", agent="mismagent:mismagent-reviewer"), "deny")
        self.assertEqual(decide("git push", agent="other-agent"), "allow")
        self.assertEqual(decide("git push", agent="mismagent-worker"), "allow")  # retired name

    def test_deny_message_names_the_conductor(self):
        reason = run("git tag R1", agent="mismagent-architect")["permissionDecisionReason"]
        self.assertIn("/mismagent:build", reason)
        self.assertIn("Commit your work", reason)

    def test_pull_denied(self):  # a pull is a merge, or a rebase
        for cmd in ("git pull", "git pull --rebase origin main", "git pull --ff-only",
                    "git -C /r pull", "git fetch && git pull"):
            self.assertEqual(decide(cmd, agent="mismagent:mismagent-builder"), "deny", cmd)
        self.assertIn("git pull (a merge, or a rebase)", run("git pull")["permissionDecisionReason"])

    def test_commit_of_everything_by_pathspec_denied(self):
        for cmd in ("git commit -m x .", "git commit -m x -- .", "git commit . -m x",
                    "git commit -m x ./", "git commit -m x :/", "git commit -m x -- src/a.py .",
                    "git commit -m x -- src/..", "git commit --message=x '*'",
                    "git commit -F msg.txt .", "git commit -C HEAD ."):
            self.assertEqual(decide(cmd), "deny", cmd)
        reason = run("git commit -m x .")["permissionDecisionReason"]
        self.assertIn("git commit of everything", reason)

    def test_a_commit_options_value_is_neither_a_pathspec_nor_an_option(self):
        for cmd in ("git commit -m .", "git commit -sm .", "git commit --message .",
                    "git commit -m. src/a.py",
                    "git commit -m 'adds the parser'", 'git commit -m"adds a.py"',
                    "git commit -uall -m x src/a.py", "git commit --amend --no-edit",
                    "git commit -m x > /dev/null 2>&1", "git commit -m x 2> err.txt -- src/a.py"):
            self.assertEqual(decide(cmd), "allow", cmd)
        for cmd in ("git commit -F . src/a.py", "git commit -F - < msg.txt"):  # no sweep: a message unread
            self.assertIn("a message the hook cannot read", run(cmd)["permissionDecisionReason"], cmd)

    def test_spellings_of_the_current_directory_denied(self):
        for cmd in ("git add ./", "git add ./.", "git add src/..", "git add src/../", "git add -- .",
                    'git add "."', "git add :/.", "git add ./*", "git add src/a.py ./"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_the_humans_commit_subjects_denied(self):  # only `mm spec` / `mm conventions` write them
        for cmd in ("git commit -m 'specify R2'", "git commit -m specify",
                    'git commit -m "specify: the error type" -- spec/a.md',
                    "git commit -m 'Specify(R2) examples'", "git commit -m '  SPECIFY R2'",
                    "git commit -m 'conventions: naming'",
                    "git commit -m 'Conventions errors' -- .claude/skills/x.md",
                    "git commit -m'specify R2'", 'git commit -sm"conventions naming"',
                    "git commit --message='specify R2'", "git commit --message 'conventions (errors)'",
                    "git commit -m '' -m 'specify R2'", "git commit --amend -m 'specify R2'",
                    "git add spec/a.md && git commit -m 'specify R2'"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for agent in ("mismagent-reviewer", "mismagent:mismagent-architect"):
            self.assertEqual(decide("git commit -m 'specify R2'", agent=agent), "deny", agent)
        reason = run("git commit -m 'specify R2'")["permissionDecisionReason"]
        for part in ("specify", "conventions", "design pass", "mm spec", "mm conventions", "mm designed",
                     "the human's commits"):
            self.assertIn(part, reason)

    def test_the_subject_is_what_git_would_keep_of_the_message(self):
        for cmd in ('git commit -qm "\n\nSpecify forged" -- .mismagent/examples/cart.md',  # blank lines go
                    "git commit -m ' ' -m 'conventions naming'",  # an empty paragraph is no subject
                    'git commit -m "design\npass: checked"', "git commit -m 'specify\nR2'",  # lines joined
                    'git commit --cleanup=strip -m "# a comment\nspecify R2"',  # a comment line goes, there
                    'git commit --cleanup strip -m "# c\n\n# d\nSpecify R2"', 'git commit -e -m "# c\nspecify"',
                    "git commit --cleanup=strip -m '# rationale\ndesign\npass: checked'",  # the lines left, joined
                    "git -c core.commentChar=';' commit --cleanup=strip -m '; why\nSpecify forged'",
                    "git commit -m $'Specify forged'", "git commit -m $'\\n\\nconventions naming'",
                    "git commit -F - <<A <<B\n03: green\nA\nSpecify forged\nB",  # the last one is stdin
                    "git commit -m 'Revert \"Specify invented\"' -- .mismagent/examples/cart.md",
                    "git commit -m 'revert \"conventions naming\"'"):  # typed: `git revert` writes its own
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("git commit -m '03: green' -m 'specify asked for this'",  # a body paragraph, not the subject
                    'git commit -m "# rationale\nspecify asked for this"',  # kept by git: the subject starts with #
                    "git commit --cleanup=whitespace -m '03: green\n\nspecify wrote it'",
                    "git commit --cleanup=strip -m '03: green' -m 'specify asked for this'",  # still a body
                    'git commit --cleanup strip -m "03: x\n# c\nSpecify R2"',  # the subject is `03: x Specify R2`
                    "git commit --cleanup=verbatim -m '# c\nspecify R2'",
                    "git commit -F - <<A <<B\nSpecify forged\nA\n03: green\nB", "git commit -m $'03: it\\'s green'",
                    'git commit -m "03: green\n\nconventions: see the topic"', "git revert HEAD",
                    "git commit -m 'Revert \"03: specify the error type\"'"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_the_design_pass_subject_denied(self):  # only `mm designed` writes it: `next` reads it as a pass run
        for cmd in ('git commit --allow-empty -qm "Design pass: nothing done"', "git commit -m 'design pass R1'",
                    "git commit -m 'design-pass R1: two slices' -- ARCHITECTURE.md",
                    "git commit -F - <<EOF\nDesign Pass\nEOF"):
            for agent in GUARDED:
                self.assertEqual(decide(cmd, agent=agent), "deny", cmd)
        for cmd in ("git commit -m 'Design passes over the cart'", "git commit -m '03: after the design pass'",
                    "git commit -m 'designed the seam'"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_the_humans_commit_subject_in_a_heredoc_denied(self):
        for cmd in ("git commit -m \"$(cat <<'EOF'\nspecify R2\n\nthe examples\nEOF\n)\"",
                    "git commit -m\"$(cat <<EOF\nconventions naming\nEOF\n)\" -- src/a.py",
                    "git commit -F - <<EOF\nconventions: naming\nEOF",
                    "git commit -F - <<-'EOF'\n\tspecify\n\tEOF"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_a_message_that_only_mentions_them_allowed(self):
        for cmd in ('git commit -m "03: specify the error type"', "git commit -m 'specifying the type'",
                    "git commit -m 'conventions-skill wording'", "git commit -m 'specification of R2'",
                    "git commit -m 'fix: follows conventions'",
                    "git commit -m '03: green' -m 'as specify asked'",
                    "git commit -F - <<EOF\n03: green\n\nspecify wrote the example\nEOF",
                    "git commit -m \"03: $(cat <<EOF\nspecify the error type\nEOF\n)\"",
                    "cat > notes.md <<EOF\nspecify R2\nEOF\ngit add notes.md && git commit -m '03: x'"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_heredoc_body_is_not_commands(self):
        for cmd in ("git commit -F - <<EOF\nslice 03\ngit merge was not needed here\nEOF",
                    "git commit -F - <<'EOF'\nslice 03\ngit push; git add -A\nEOF",
                    'git commit -F - <<"EOF"\nslice 03\ngit rebase main\nEOF',
                    "git commit -F - <<-EOF\n\tslice 03\n\tgit stash\n\tEOF",
                    "git commit -m \"$(cat <<'EOF'\n03: it's \"green\"\n\ngit pull, unneeded\nEOF\n)\"",
                    "cat > a.md <<A; cat > b.md <<B\ngit push\nA\ngit tag R1\nB\ngit status"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_a_command_after_the_heredoc_is_still_judged(self):
        for cmd in ("git commit -F - <<EOF\nslice 03\nEOF\ngit push",
                    "git commit -F - <<-'EOF'\n\tslice 03\n\tEOF\ngit merge x",
                    "cat > a.md <<A; cat > b.md <<B\nx\nA\ny\nB\ngit tag R1",
                    "cat <<EOF | git push\nx\nEOF",
                    "git commit -F - <<EOF && git push\nslice 03\nEOF"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_an_unterminated_heredoc_or_a_lookalike_hides_nothing(self):
        for cmd in ("cat <<EOF\nslice 03\ngit push", "echo $((1<<2))\ngit push",
                    "cat <<< EOF\ngit push\nEOF", 'git commit -m "a << b"\ngit push'):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_a_heredoc_lookalike_in_a_string_hides_no_command(self):
        for cmd in ("printf '%s\n' '<<true'\ngit add -A\ngit commit -qm 'x'\ntrue",  # quoted: it opens nothing
                    'echo "<<EOF"\ngit push\nEOF', "echo \\<<EOF\ngit push\nEOF",
                    "# don't\nprintf '%s\n' '<<true'\ngit add -A\ntrue",  # nor does a comment open a string
                    "echo $'it\\'s' '<<EOF'\ngit push\nEOF"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_a_heredoc_the_shell_would_run_is_judged(self):
        for cmd in ("cat <<EOF\n$(git add -A)\nEOF", "cat <<EOF\nx `git push` y\nEOF",  # expanded by the shell
                    "git commit -F - <<EOF\n03: green $(git stash)\nEOF",
                    "bash <<'EOF'\ngit add -A\nEOF", "cat <<'EOF' | sh\ngit push\nEOF",  # read by a shell
                    "sh -s <<EOF\ngit merge x\nEOF"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("cat > a.md <<'EOF'\n$(git add -A) is what the hook denies\nEOF",  # quoted: never expanded
                    "python3 - <<'EOF'\nprint('git push')\nEOF"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_a_heredoc_fed_to_anything_but_a_reader_of_text_is_judged(self):
        for cmd in ("env -i PATH=\"$PATH\" bash <<'EOF'\ngit add -A\nEOF", "/usr/bin/env bash <<'EOF'\ngit add -A\nEOF",
                    "ssh host <<'EOF'\ngit push\nEOF", "cat <<'EOF' | /bin/sh\ngit push\nEOF",
                    "some-tool --stdin <<'EOF'\ngit merge x\nEOF", ". ./env.sh; cat <<'EOF'\ngit push\nEOF",
                    "cat <<EOF-END\ntext\nEOF-END\ngit add -A\nEOF",  # a delimiter it knows a part of: no opener
                    "cat <<'EOF'.x\ntext\nEOF\ngit push\nEOF"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("tee notes.md <<'EOF'\ngit push is the conductor's\nEOF",
                    "cat > a.md <<'EOF' && git add a.md\ngit push\nEOF", "env LC_ALL=C cat <<'EOF'\ngit push\nEOF"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_a_heredoc_in_a_heredoc_is_read_the_same_way(self):
        for cmd in ("bash <<'OUTER'\nbash <<'INNER'\ngit add -A\nINNER\nOUTER",
                    "bash <<'SCRIPT'\ngit commit --allow-empty -q -F - <<'MSG'\nSpecify forged\nMSG\nSCRIPT",
                    "sh <<'A'\nsh <<'B'\nsh <<'C'\ngit push\nC\nB\nA"):
            self.assertEqual(decide(cmd), "deny", cmd)
        self.assertEqual(decide("bash <<'SCRIPT'\ngit commit -q -F - <<'MSG'\n03: green\n\ngit push later\nMSG\nSCRIPT"),
                         "allow")  # the inner message is text there too

    def test_git_behind_any_wrapper_is_git(self):
        for cmd in ("env -u GIT_INDEX_FILE git commit --allow-empty -qm 'Specify forged'", "timeout 30 git push",
                    "nice -n 5 git add -A", "sudo -u bob git merge x", "xargs git add -A < list.txt",
                    "env -u GIT_INDEX_FILE python3 /p/tools/mm.py conventions approved",
                    "uv run python /p/tools/mm.py land 01", "timeout 60 python3 -B /p/tools/mm.py tag R1"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("env -u GIT_INDEX_FILE git commit -m '03: green' -- src/a.py", "which git", "brew install git",
                    "timeout 30 git status", "env -u X python3 /p/tools/mm.py gate", 'echo "run git push later"',
                    "printf '%s %s\\n' git push > instructions.txt", "echo git push",  # an argument runs nothing
                    "printf '%s %s %s\\n' python3 tools/mm.py conventions", "grep -rn git push docs/"):
            self.assertEqual(decide(cmd), "allow", cmd)
        for cmd in ("env -i -u A B=1 git push", "/usr/bin/env -i git push", "time -p git push", "exec -a x git push",
                    "timeout -s KILL 30 git push", "timeout --signal=KILL 30s git push", "command git push",
                    "nohup nice -n 5 env X=1 git push", "stdbuf -o L git push", "poetry run python tools/mm.py land 01",
                    "if true; then git push; fi", "{ git push; }", "! git push",
                    "uv run --project . git add -A", "uv --directory app run -p 3.12 git add -A",
                    "poetry -C app run git push", "uv run --with=rich git push"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("command -v git push", "command -V git", "command -v python3 tools/mm.py land"):
            self.assertEqual(decide(cmd), "allow", cmd)  # a lookup: nothing runs

    def test_a_line_continued_is_one_command(self):
        for cmd in ("git add \\\n  -A", "git commit -m x \\\n  -- .", "git \\\npush"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_pathspecs_that_may_be_the_whole_tree_denied(self):
        for cmd in ("git add ':(top)'", "git commit -qm '03: green' -- ':(top)**'", "git add ':(glob)**'",
                    "git add '**'", "git add '*/*'", "git add ..", "git add ../..", "git add ':!secret'",
                    "git commit -m x ':^a'", "git commit -m x ..", "git commit -m x -- '**'"):
            self.assertEqual(decide(cmd), "deny", cmd)
        for cmd in ("git add ../src/a.py", "git add 'src/*.py'", "git add src/**/a.py",
                    "git commit -m x -- ../src/a.py", "git commit -m ':/ is the root'",
                    "git add ':(literal)src/a.py'", "git commit -m x -- ':(literal)src/a.py'"):
            self.assertEqual(decide(cmd), "allow", cmd)
        self.assertEqual(decide("git add ':(literal).'"), "deny")

    def test_an_mm_subcommand_of_another_role_denied(self):
        mm = 'python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" '
        allowed = {"mismagent-builder": ("built 01 --friction none", "shot 01"),
                   "mismagent-reviewer": ("review 01 PASS --sha abc1234", "shot R1"),
                   "mismagent-architect": ('spec "stack review 2"', 'designed "R1: nothing"', "review 01 DIRECT --sha a")}
        for agent, own in allowed.items():
            for call in own + ("gate --base abc1234", "check", "status", "next --json", "log"):
                self.assertEqual(decide(mm + call, agent=agent), "allow", (agent, call))
            for other in (c for a, calls in allowed.items() if a != agent for c in calls
                          if c.split()[0] not in [x.split()[0] for x in own] + ["shot"]):  # shot: anybody's
                self.assertEqual(decide(mm + other, agent=agent), "deny", (agent, other))
            for call in ("start 01", "park 01", "land 01", "tag R1", 'conventions "errors: updated"'):
                self.assertEqual(decide(mm + call, agent=agent), "deny", (agent, call))
                self.assertIsNone(run(mm + call, agent=None), call)  # the conductor, the human's session
        for cmd in ("cd app && python3 /p/tools/mm.py land 01", "MM_LOCK_WAIT=1 python3 ../tools/mm.py tag R1",
                    "python3 /p/tools/mm.py gate && python3 /p/tools/mm.py conventions x"):
            self.assertEqual(decide(cmd), "deny", cmd)
        reason = run(mm + "designed x")["permissionDecisionReason"]
        self.assertIn("mm designed (the architect's)", reason)
        for cmd in ("cat tools/mm.py | grep land", "cat tools/mm.py conventions", "grep -n land tools/mm.py",
                    mm + "--help conventions", mm + "land --help", "python3 -m pytest tests/test_mm.py land"):
            self.assertEqual(decide(cmd), "allow", cmd)  # reading it, or its help, is no call
        for cmd in ("python3 /p/tools/mm.py $'conventions' approved", "/usr/bin/env python3 -B /p/tools/mm.py land 01",
                    "env -i python3.12 /p/tools/mm.py tag R1", "/p/tools/mm.py land 01"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_each_agents_prompt_names_only_the_mm_subcommands_it_may_run(self):
        agents = os.path.join(os.path.dirname(HOOK), os.pardir, "agents")
        for agent in GUARDED:
            with open(os.path.join(agents, agent + ".md"), encoding="utf-8") as f:
                subs = set(mm_calls(f.read()))
            self.assertTrue(subs, agent)
            for sub in subs:
                self.assertEqual(decide('python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" %s x' % sub, agent=agent),
                                 "allow", (agent, sub))

    def test_left_to_the_agents_on_purpose(self):
        """Pinned so nobody "fixes" them: how a builder brings its worktree's code in, reworks its
        own commits and commits by path."""
        for cmd in ("git cherry-pick abc1234", "git cherry-pick main..slice-03", "git commit --amend",
                    "git commit --amend -m '03: green'", "git reset --soft HEAD~1", "git reset",
                    "git reset HEAD src/a.py", "git revert HEAD", "git revert --no-edit abc1234",
                    "git worktree add ../wt-03 -b slice-03", "git commit -m x -- src/a.py tests/b.py",
                    "git commit -m x src/a.py", 'git commit -m "03: specify the error type"',
                    "git add src/", "git add ./src/a.py", "git add src/../tests/b.py",
                    "git fetch origin"):
            self.assertEqual(decide(cmd, agent="mismagent:mismagent-builder"), "allow", cmd)

    def test_main_session_untouched_by_the_new_rules(self):
        for cmd in ("git pull", "git commit -m 'specify R2' .", "git add ./", "git commit -m x -- ."):
            self.assertIsNone(run(cmd, agent=None), cmd)
            self.assertIsNone(run(cmd, agent=""), cmd)


class MessageSources(unittest.TestCase):
    """A subject the command does not spell: in a file, reused from a commit, kept by an amend."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.git("init", "-q")
        os.makedirs(os.path.join(self.dir, "sub"))
        self.human = self.commit("specify R1: EX-4")
        self.mine = self.commit("03: green")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=self.dir,
                              capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, subject):
        self.git("commit", "-q", "--allow-empty", "-m", subject)
        return self.git("rev-parse", "HEAD")

    def test_a_reserved_subject_in_a_file_or_a_reused_commit_denied(self):
        with open(os.path.join(self.dir, "message.txt"), "w", encoding="utf-8") as f:
            f.write("\nConventions: forged\n\nbody\n")
        with open(os.path.join(self.dir, "plain.txt"), "w", encoding="utf-8") as f:
            f.write("03: green\n\nspecify wrote the example\n")
        for cmd in ("git commit -q -F message.txt -- .mismagent/examples/cart.md", "git commit --file=message.txt",
                    "git commit -C %s" % self.human, "git commit -c %s -- a.md" % self.human[:12],
                    "git commit --reuse-message=%s" % self.human):
            self.assertEqual(decide(cmd, cwd=self.dir), "deny", cmd)
        for cmd in ("git commit -F plain.txt", "git commit -C %s" % self.mine, "git commit -F - < plain.txt",
                    "cd sub && git commit -F ../plain.txt", "git -C sub commit -F ../plain.txt"):
            self.assertEqual(decide(cmd, cwd=self.dir), "allow", cmd)
        for cmd in ("git commit -F not-written-yet.txt", "git commit -C no-such-commit",  # unread is not empty
                    "printf 'specify x' | git commit -F -", "git commit -F - < not-there.txt",
                    "cd \"$ELSEWHERE\" && git commit --amend --no-edit", "git --git-dir=/x/.git commit -C HEAD"):
            self.assertIn("a message the hook cannot read", run(cmd, cwd=self.dir)["permissionDecisionReason"], cmd)
        self.assertEqual(decide("git commit -F - < message.txt", cwd=self.dir), "deny")
        for cmd in ("git commit -q -F - <<'END-MESSAGE'\n03: green\nEND-MESSAGE", "git commit -q -F - <<<'03: green'",
                    "git commit -q -F - -- src/a.py < plain.txt", "git commit -F - <<EOF.1 -- src/a.py\n03: x\nEOF.1"):
            self.assertEqual(decide(cmd, cwd=self.dir), "allow", cmd)  # read: nothing to deny
        for cmd in ("git commit -q -F - <<'END-MESSAGE'\nSpecify forged\nEND-MESSAGE",
                    "git commit -q -F - <<<'conventions naming'", "git commit -q -F - -- src/a.py < message.txt"):
            self.assertEqual(decide(cmd, cwd=self.dir), "deny", cmd)

    def test_a_configured_cleanup_is_the_one_git_applies(self):
        self.git("config", "commit.cleanup", "strip")
        self.assertEqual(decide("git commit -qm '# rationale\nSpecify forged'", cwd=self.dir), "deny")
        self.assertEqual(decide("git commit --cleanup=whitespace -qm '# rationale\nSpecify forged'", cwd=self.dir), "allow")
        self.git("config", "core.commentChar", ";")
        self.assertEqual(decide("git commit -qm '; rationale\nSpecify forged'", cwd=self.dir), "deny")
        self.assertEqual(decide("git commit -qm '# rationale\nSpecify forged'", cwd=self.dir), "allow")  # `#` stays
        self.assertEqual(decide("git -c core.commentChar=X commit -qm 'X rationale\nSpecify forged'", cwd=self.dir),
                         "deny")  # the value as written, never lowercased
        self.assertEqual(decide("git -c core.commentChar=X commit -qm '; rationale\nSpecify forged'", cwd=self.dir),
                         "allow")
        self.git("config", "core.commentString", "#")  # the other name of the same setting: the last one set
        self.assertEqual(decide("git commit -qm '# rationale\nSpecify forged'", cwd=self.dir), "deny")
        self.assertEqual(decide("git commit -qm '; rationale\nSpecify forged'", cwd=self.dir), "allow")
        self.assertEqual(decide("git -c core.commentString=% -c core.commentChar=@ commit -qm '@ why\nspecify R2'",
                                cwd=self.dir), "deny")

    def test_the_message_is_read_where_git_runs(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other)
        for where, text in ((self.dir, "03: green\n"), (os.path.join(self.dir, "sub"), "Conventions: forged\n"),
                            (other, "specify R9\n")):
            with open(os.path.join(where, "message.txt"), "w", encoding="utf-8") as f:
                f.write(text)
        subprocess.run(["git", "init", "-q"], cwd=other, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q",
                        "--allow-empty", "-m", "Conventions: approved"], cwd=other, check=True)
        self.assertEqual(decide("git commit -F message.txt", cwd=self.dir), "allow")
        for cmd in ("git -C sub commit -q -F message.txt -- ../.mismagent/examples/cart.md",
                    "cd sub && git commit -F message.txt", "cd sub; cd . ; git commit -F message.txt",
                    "git -C %s commit --allow-empty -C HEAD" % other, "git -C %s commit --amend --no-edit" % other,
                    "cd %s && git commit --amend --no-edit" % other, "cd sub && git -C %s commit -F message.txt" % other,
                    "pushd %s; git commit -F message.txt" % other):
            self.assertEqual(decide(cmd, cwd=self.dir), "deny", cmd)
        for cmd in ("pushd -n sub; git commit -F message.txt", "cd -P sub && git commit -F message.txt",
                    "uv run --directory sub git commit -F message.txt",  # a wrapper's own move: not followed
                    "cd \"$(pwd)/sub\" && git commit --amend --no-edit"):  # an option, a substitution: where, then?
            self.assertIn("a message the hook cannot read", run(cmd, cwd=self.dir)["permissionDecisionReason"], cmd)
        for cmd in ("pushd sub; popd; git commit -F message.txt", "pushd sub; pushd ..; popd; popd; git commit -F message.txt",
                    "(cd sub && pwd); git commit -F message.txt",  # the group's move ended with it: the root's file
                    "x=$(cd sub && pwd); git commit -F message.txt", "(cd sub; (cd ..; pwd)); git commit -F message.txt",
                    "{ cd sub; }; git commit -F ../message.txt", "cd sub && git commit -F ../message.txt",
                    "env -C sub git commit -F ../message.txt", "uv run --directory sub git commit -m '03: green'",
                    "bash <<'S'\ngit commit -q -F message.txt\nS\ncd sub"):  # fed here, before the cd
            self.assertEqual(decide(cmd, cwd=self.dir), "allow", cmd)
        for cmd in ("(cd sub && git commit -F message.txt)", "{ cd sub; }; git commit -F message.txt",
                    "env -C sub git commit -q -F message.txt", "env --chdir=sub X=1 git commit -F message.txt",
                    "cd sub\nbash <<'S'\ngit commit -q -F message.txt\nS\ncd ..",  # fed in sub
                    "(cd sub; bash <<'S'\ngit commit -q -F message.txt\nS\n)"):
            self.assertEqual(decide(cmd, cwd=self.dir), "deny", cmd)
        self.assertEqual(decide("pushd sub; pushd ..; popd; git commit -F message.txt", cwd=self.dir), "deny")  # in sub
        self.assertEqual(decide("git add %s" % self.dir, cwd=os.path.join(self.dir, "sub")), "deny")  # the root, absolute
        self.assertEqual(decide("(cd sub); git add %s" % self.dir, cwd=self.dir), "deny")  # wherever the hook stands
        self.assertEqual(decide("git add %s/" % os.path.dirname(self.dir), cwd=self.dir), "deny")
        self.assertEqual(decide("git add %s/sub/a.py" % self.dir, cwd=self.dir), "allow")

    def test_an_amend_that_keeps_a_reserved_subject_denied(self):
        for cmd in ("git commit --amend", "git commit --amend --no-edit -- src/a.py"):
            self.assertEqual(decide(cmd, cwd=self.dir), "allow", cmd)  # HEAD is the builder's own
        self.commit("Design pass: R1")
        for cmd in ("git commit --amend", "git commit --amend --no-edit -- src/a.py"):
            self.assertEqual(decide(cmd, cwd=self.dir), "deny", cmd)  # the amended commit would keep it
        self.assertEqual(decide("git commit --amend -m '03: green'", cwd=self.dir), "allow")  # reworded: its own


if __name__ == "__main__":
    unittest.main()
