"""Tests for hooks/guard-human.py — stdlib unittest; feeds a PreToolUse event on stdin.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "hooks", "guard-human.py")


def run(path, agent="mismagent-builder", tool="Write", key="file_path"):
    event = {"tool_name": tool, "tool_input": {key: path}}
    if agent is not None:
        event["agent_type"] = agent
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True,
                         text=True, check=True).stdout.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


def decide(path, **kw):
    out = run(path, **kw)
    return out["permissionDecision"] if out else "allow"


class GuardHuman(unittest.TestCase):
    def test_human_files_denied(self):
        for path in ("/r/REQUISITI.md", "/r/docs/REQUISITI-R2.md", "/r/requisiti_v2.md",
                     "/r/requirements.md", "/r/Requirements-R1.md", "REQUIREMENTS.MD",
                     "/r/.mismagent/examples.md", ".mismagent/examples.md",
                     "/r/.mismagent/examples/delete-project.md", ".mismagent/examples/search.md",
                     "/r/.claude/skills/conventions/SKILL.md",
                     ".claude/skills/conventions/references/errors.md"):
            self.assertEqual(decide(path), "deny", path)

    def test_every_editing_tool_guarded(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertEqual(decide("/r/REQUISITI.md", tool=tool), "deny", tool)
        self.assertEqual(decide("/r/requirements.md", tool="NotebookEdit", key="notebook_path"),
                         "deny")

    def test_other_files_allowed(self):
        for path in ("/r/src/requirements.py", "/r/requirements.txt", "/r/ARCHITECTURE.md",
                     "/r/.mismagent/slices/S1.md", "/r/docs/examples.md", "/r/docs/examples/a.md",
                     "/r/.mismagent/releases/R0.md", "/r/.mismagent/decisions/0001-x.md",
                     "/r/.mismagent/examples.md.bak", "/r/my-requirements.md",
                     "/r/.mismagent/conventions-proposals.md", "/r/.claude/skills/other/SKILL.md"):
            self.assertEqual(decide(path), "allow", path)

    def test_all_three_agents_guarded(self):
        for agent in ("mismagent-builder", "mismagent-reviewer", "mismagent-architect",
                      "mismagent:mismagent-architect"):
            self.assertEqual(decide("/r/REQUISITI.md", agent=agent), "deny", agent)

    def test_main_session_and_other_agents_allowed(self):
        self.assertEqual(decide("/r/REQUISITI.md", agent=None), "allow")
        self.assertEqual(decide("/r/REQUISITI.md", agent=""), "allow")
        self.assertEqual(decide("/r/REQUISITI.md", agent="other-agent"), "allow")

    def test_deny_message_points_to_a_question(self):
        reason = run("/r/.mismagent/examples.md")["permissionDecisionReason"]
        self.assertIn("belong to the human", reason)
        self.assertIn("Question in the slice file", reason)


if __name__ == "__main__":
    unittest.main()
