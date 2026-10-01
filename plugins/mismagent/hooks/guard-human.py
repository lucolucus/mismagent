#!/usr/bin/env python3
"""PreToolUse(Edit|Write|MultiEdit|NotebookEdit) guard: the builder, the reviewer and the architect
never write the human's files — the requirements (REQUISITI*.md, requirements*.md, any case),
.mismagent/examples.md and the conventions skill (.claude/skills/conventions/). A doubt becomes a
Question in the slice file; a convention, a line in .mismagent/conventions-proposals.md. Main-session calls pass
untouched. A courtesy like guard-git.py: it reads the tool's path, not what a Bash command writes.
"""
import fnmatch
import json
import os
import sys

GUARDED = ("mismagent-builder", "mismagent-reviewer", "mismagent-architect")
HUMAN_NAMES = ("requisiti*.md", "requirements*.md")
HUMAN_SUFFIX = ".mismagent/examples.md"
HUMAN_DIR = ".claude/skills/conventions/"


def human_file(path):
    norm = path.replace("\\", "/")
    base = os.path.basename(norm).lower()
    if any(fnmatch.fnmatchcase(base, pattern) for pattern in HUMAN_NAMES):
        return True
    return (norm == HUMAN_SUFFIX or norm.endswith("/" + HUMAN_SUFFIX)
            or norm.startswith(HUMAN_DIR) or "/" + HUMAN_DIR in norm)


try:
    event = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
agent = event.get("agent_type") or ""  # absent in the main session
if agent.split(":")[-1] not in GUARDED:  # tolerate a plugin-namespaced type
    sys.exit(0)
tool_input = event.get("tool_input") or {}
path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
if path and human_file(path):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "%s is denied to %s: these files belong to the human. Write a Question in the slice "
            "file instead (a convention: a line in .mismagent/conventions-proposals.md)." % (path, agent)),
    }}))
sys.exit(0)
