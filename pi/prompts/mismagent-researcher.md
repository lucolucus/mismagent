---
description: "Invoke mismAgent's researcher (explore movement) \u2014 dispatches the mismagent-researcher subagent to explore a domain/topic and gather material into research/<topic>.md. Use only when a decision needs investigation AND the topic unblocks something downstream."
argument-hint: "[topic / question to research]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

Dispatch the **`mismagent-researcher`** subagent (the `subagent` tool) on `$ARGUMENTS`. Frame what it unblocks
downstream (a decision by the analyst? an ADR?); if nothing → it returns `NEEDS-SCOPE` and writes
nothing. Output: `research/<topic>.md`, cited later by an ADR. See `agents/mismagent-researcher.md`.
