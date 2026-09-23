#!/usr/bin/env python3
"""PreToolUse(Bash) guard: workers and the verifier never merge, push, rebase, hard-reset or move
block state — the worker-composer does. Main-session calls pass untouched.

It splits the command on `&&`, `||`, `;`, `|`, `&` and newlines, tokenizes each segment (shlex),
skips env assignments and git's global options (`-C <path>`, `-c <kv>`, `--no-pager`, …), then
judges the git subcommand. Partial protection by design: it reads the literal command text, so an
indirection (a script, an alias, `eval`, `sh -c`, a variable) can slip past. It backs the prompts'
invariant; it does not replace it.
"""
import json
import os
import re
import shlex
import sys

GUARDED = ("mismagent-worker", "mismagent-verifier")
# global options that consume the next token as their value (the `--opt=value` form needs no skip)
TAKES_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
PREFIXES = {"env", "command", "exec", "time", "nohup", "sudo", "then", "do", "else", "!", "{"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def tokens(command):
    command = command.replace("\n", " ; ")
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:  # unbalanced quotes: fall back to a plain split
        return re.split(r"\s+|(?=[;&|()])|(?<=[;&|()])", command)


def segments(command):
    current = []
    for tok in tokens(command):
        if tok and set(tok) <= set(";&|()"):
            if current:
                yield current
            current = []
        elif tok:
            current.append(tok)
    if current:
        yield current


def git_call(seg):
    """(subcommand, args) if the segment runs git, else None."""
    i = 0
    while i < len(seg) and (ASSIGNMENT.match(seg[i]) or seg[i] in PREFIXES):
        i += 1
    if i >= len(seg) or os.path.basename(seg[i]) != "git":
        return None
    i += 1
    while i < len(seg) and seg[i].startswith("-"):
        i += 2 if seg[i] in TAKES_VALUE else 1
    if i >= len(seg):
        return None
    return seg[i], seg[i + 1:]


def violation(sub, args):
    if sub in ("merge", "push", "rebase"):
        return "git " + sub
    if sub == "reset" and "--hard" in args:
        return "git reset --hard"
    if sub == "mv" and any(re.search(r"(^|/)blocks/", a) for a in args):
        return "git mv of a block's state"
    return None


try:
    event = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
agent = event.get("agent_type") or ""  # absent in the main session
if agent.split(":")[-1] not in GUARDED:  # tolerate a plugin-namespaced type
    sys.exit(0)
command = (event.get("tool_input") or {}).get("command") or ""
for seg in segments(command):
    call = git_call(seg)
    what = call and violation(*call)
    if what:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "%s is denied to %s: merges and state moves belong to the worker-composer "
                "(/mismagent:worker-composer). Leave your work on your branch and return your "
                "result." % (what, agent)),
        }}))
        break
sys.exit(0)
