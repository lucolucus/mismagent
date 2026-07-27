---
description: "Invoke mismAgent's tactical modeler (model movement) \u2014 dispatches the mismagent-tactical-modeler subagent to complete the DDD tactical level per context (aggregates, invariants, domain events, commands+actor) into the context-map, absorbing the Seeds. Use at the start of model."
argument-hint: "[feature / context]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

**Re-entrance guard:** if the context-map's **"Tactical model" section is already written**, do not
re-dispatch from scratch — say so and ask what to deepen or reopen (which context, which
invariant/command), then dispatch with that named scope (friction-log-4 #14).

Otherwise dispatch the **`mismagent-tactical-modeler`** subagent (the `subagent` tool) on `$ARGUMENTS`. It starts from the
context-map's "Seeds for the tactical" and writes the **Tactical model** section (every line with a
downstream consumer: invariants→AC, commands→write, events→read-model). On `NEEDS-INPUT` it brings you
the ambiguities — you decide. See `agents/mismagent-tactical-modeler.md`.
