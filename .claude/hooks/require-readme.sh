#!/bin/sh
# PreToolUse(Bash) — block a `git commit` that does not carry a README.md update.
# README counts as updated when it is already staged, or when it is modified in the
# working tree and the same command stages it (`git add -A` / `.` / `README.md`).
# Escape hatch for commits that genuinely change nothing a reader sees: put
# `[skip-readme]` in the commit command (e.g. in the message).
cmd=$(jq -r '.tool_input.command // ""')

case "$cmd" in
  *"git commit"*|*"git -C "*" commit"*) ;;
  *) exit 0 ;;
esac
case "$cmd" in *"[skip-readme]"*) exit 0 ;; esac

repo="${CLAUDE_PROJECT_DIR:-.}"
git -C "$repo" diff --cached --name-only -- README.md | grep -q . && exit 0
if git -C "$repo" diff --name-only -- README.md | grep -q . &&
   printf '%s' "$cmd" | grep -Eq 'git (-C [^ ]+ )?add ([^&;|]* )?(-A|--all|\.|README\.md)( |$|&|;)'; then
  exit 0
fi

jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny",
  permissionDecisionReason: "README.md is not part of this commit. Update README.md to reflect the change (version note, command table, layout — whatever the commit touches), stage it, then commit again. If the commit truly changes nothing a README reader sees, add [skip-readme] to the commit message."}}'
