---
description: Invoke mismAgent's tactical modeler (model movement) — dispatches the mismagent-tactical-modeler subagent to complete the DDD tactical level per context (aggregates, invariants, domain events, commands+actor) into the context-map, absorbing the Seeds. Use at the start of model.
argument-hint: "[feature / context]"
---

Dispatch the **`mismagent-tactical-modeler`** subagent (Agent tool) on `$ARGUMENTS`. It starts from the
context-map's "Seeds for the tactical" and writes the **Tactical model** section (every line with a
downstream consumer: invariants→AC, commands→write, events→read-model). On `NEEDS-INPUT` it brings you
the ambiguities — you decide. See `agents/mismagent-tactical-modeler.md`.
