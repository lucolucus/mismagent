"""Tests for hooks/guard-git.py — stdlib unittest; feeds a PreToolUse event on stdin.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "hooks", "guard-git.py")


def run(command, agent="mismagent-builder"):
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent is not None:
        event["agent_type"] = agent
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True,
                         text=True, check=True).stdout.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


def decide(command, agent="mismagent-builder"):
    out = run(command, agent)
    return out["permissionDecision"] if out else "allow"


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
                    "git add -A && git status", 'echo "git push" > notes.txt',
                    "git commit -m 'S1 green'", "git add . && git commit -am wip",
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


if __name__ == "__main__":
    unittest.main()
