---
description: "Invoke mismAgent's analyst (explore movement) \u2014 dispatches the mismagent-analyst subagent to model the STRATEGIC domain (bounded contexts + relationships), fix the UBIQUITOUS LANGUAGE (amending the PROJECT context-map.md, never re-forking it) and the Seeds for the tactical (written to the feature's tactical-model.md). Use in explore after the idea survives the challenger."
argument-hint: "[what survived / domain notes]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

**Re-entrance guard:** if the project's `<output_dir>/context-map.md` **already covers this
feature's contexts**
(bounded contexts + ubiquitous language), do not re-model from scratch — say so and ask what to
extend or reopen (a new context? a name to re-fix?), then dispatch with that named scope
(friction-log-4 #14).

Otherwise dispatch the **`mismagent-analyst`** subagent (the `subagent` tool) on `$ARGUMENTS` (or what survived the
challenger). Fix with me the **ubiquitous language** (one concept = one canonical name). On
`NEEDS-INPUT` bring the `AMBIGUITIES` to me and re-dispatch. Output: the project `context-map.md` (strategic) + the feature's `tactical-model.md` (seeds) (
ubiquitous language + Seeds for the tactical). See `agents/mismagent-analyst.md`.
