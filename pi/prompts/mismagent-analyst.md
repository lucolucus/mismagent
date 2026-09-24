---
description: "Dispatch mismAgent's analyst (explore movement): bounded contexts, relationships and ubiquitous language amended into the project context-map, tactical seeds into the feature. Use after the idea survives the challenger."
argument-hint: "[what survived / domain notes]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md, Setup);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

**Re-entrance guard:** if the project's `<output_dir>/context-map.md` already covers this
feature's contexts, do not re-model from scratch — say so and ask what to extend or reopen, then
dispatch with that named scope.

Otherwise dispatch the **`mismagent-analyst`** subagent (the `subagent` tool) on `$ARGUMENTS` (or what survived the
challenger), **passing it the existing `<output_dir>/context-map.md` as authoritative** when one
exists: it **amends** that map — adds the contexts and terms this feature introduces, reuses the
rest verbatim — and never starts a second one. Fix with me the **ubiquitous language** (one
concept = one canonical name). On `NEEDS-INPUT` bring the `AMBIGUITIES` to me and re-dispatch.
Output: the project `context-map.md` + the seeds in the feature's `tactical-model.md`.
See `agents/mismagent-analyst.md`.
