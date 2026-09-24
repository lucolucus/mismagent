---
description: "Dispatch mismAgent's tactical modeler (model movement): aggregates, invariants, domain events and commands per context into the feature's tactical-model.md, absorbing the seeds. Use at the start of model."
argument-hint: "[feature / context]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md, Setup);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

**Re-entrance guard:** if the feature's `tactical-model.md` already has its "Tactical model"
sections, do not re-dispatch from scratch — say so and ask what to deepen or reopen, then dispatch
with that named scope.

Otherwise dispatch the **`mismagent-tactical-modeler`** subagent (the `subagent` tool) on `$ARGUMENTS`. It starts from the
"Seeds for the tactical" of `features/<feature>/tactical-model.md` and writes the **Tactical model**
sections there (every line with a reader). On `NEEDS-INPUT` it brings you
the ambiguities — you decide. See `agents/mismagent-tactical-modeler.md`.
