---
description: Dispatch mismAgent's tactical modeler (model movement): aggregates, invariants, domain events and commands per context into the feature's tactical-model.md, absorbing the seeds. Use at the start of model.
argument-hint: "[feature / context]"
---

**Re-entrance guard:** if the feature's `tactical-model.md` already has its "Tactical model"
sections, do not re-dispatch from scratch — say so and ask what to deepen or reopen, then dispatch
with that named scope.

Otherwise dispatch the **`mismagent-tactical-modeler`** subagent (Agent tool) on `$ARGUMENTS`. It starts from the
"Seeds for the tactical" of `features/<feature>/tactical-model.md` and writes the **Tactical model**
sections there (every line with a reader). On `NEEDS-INPUT` it brings you
the ambiguities — you decide; record a non-obvious answer in the feature's `decisions.md` (format:
`$CLAUDE_PLUGIN_ROOT/tools/CLI.md`). See `agents/mismagent-tactical-modeler.md`.
