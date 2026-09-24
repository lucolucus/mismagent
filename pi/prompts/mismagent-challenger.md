---
description: "Dispatch mismAgent's challenger (explore movement) with fresh context to try to demolish the idea before it is modeled. Read-only; returns KILL | RESHAPE | PROCEED. Use early in explore."
argument-hint: "[the idea / what to attack]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md, Setup);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

Dispatch the **`mismagent-challenger`** subagent (the `subagent` tool, **fresh context**) on `$ARGUMENTS` (or the
current idea/model). It is read-only and returns a **`KILL | RESHAPE | PROCEED`** verdict: on `KILL`
stop and report to me; on `RESHAPE` redesign with me; on `PROCEED` close the
`MUST_ANSWER_BEFORE_MODELING` items before going on. Record the verdict's debate and my choice in the
feature's `decisions.md` (format: `.agents/skills/mismagent-worker-composer/references/CLI.md`). See `agents/mismagent-challenger.md`.
