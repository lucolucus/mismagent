"""Tests for hooks/guard-git.py — stdlib unittest; feeds a PreToolUse event on stdin.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "hooks", "guard-git.py")


def decide(command, agent="mismagent-worker"):
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent is not None:
        event["agent_type"] = agent
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True,
                         text=True, check=True).stdout.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


class GuardGit(unittest.TestCase):
    def test_plain_forbidden_commands_denied(self):
        for cmd in ("git merge feat", "git push origin x", "git rebase main",
                    "git reset --hard HEAD~1", "git mv a/blocks/ctx/todo/b.md a/blocks/ctx/doing/"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_global_option_bypasses_denied(self):
        for cmd in ('git -C "/tmp/my repo" merge x', "git --no-pager push",
                    'git -c "user.name=Some Name" rebase x', "git --git-dir=/r/.git -P push",
                    "GIT_DIR=/r git --work-tree /w reset --hard"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_later_segments_checked(self):
        for cmd in ("git status && git push", "true; git merge x", "ls | git rebase x",
                    "git diff\ngit push", "false || /usr/bin/git push"):
            self.assertEqual(decide(cmd), "deny", cmd)

    def test_main_session_allowed(self):
        self.assertEqual(decide('git -C "/tmp/my repo" merge x', agent=None), "allow")
        self.assertEqual(decide("git push", agent=""), "allow")

    def test_normal_commands_allowed_for_worker(self):
        for cmd in ("git status", "git diff main...HEAD", "git log --oneline | head",
                    "git add -A && git status", 'echo "git push" > notes.txt',
                    "git reset --soft HEAD~1", "git mv src/a.py src/b.py"):
            self.assertEqual(decide(cmd), "allow", cmd)

    def test_namespaced_agent_denied(self):
        self.assertEqual(decide("git push", agent="mismagent:mismagent-verifier"), "deny")
        self.assertEqual(decide("git push", agent="other-agent"), "allow")


if __name__ == "__main__":
    unittest.main()
