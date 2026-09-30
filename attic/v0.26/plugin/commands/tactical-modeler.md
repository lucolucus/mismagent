---
description: Dispatch mismAgent's tactical modeler (model movement): aggregates, invariants, domain events and commands per context into the feature's tactical-model.md, absorbing the seeds. Use at the start of model.
argument-hint: "[feature / context]"
---

**Re-entrance guard:** if the feature's `tactical-model.md` already has its "Tactical model"
sections, do not re-dispatch from scratch — ask what to deepen or reopen, then dispatch with that
scope.

Otherwise dispatch the **`mismagent-tactical-modeler`** subagent on `$ARGUMENTS`. It absorbs the
"Seeds for the tactical" of `features/<feature>/tactical-model.md` into its **Tactical model** sections. On `NEEDS-INPUT` it brings you the ambiguities — you decide. Record its `DECISIONS`
and your non-obvious answers in the feature's `decisions.md` with
`python3 "${CLAUDE_PLUGIN_ROOT}/tools/mismagent.py" why append <file> --entry <entry-file>` (format:
`${CLAUDE_PLUGIN_ROOT}/tools/CLI.md`). See `agents/mismagent-tactical-modeler.md`.
