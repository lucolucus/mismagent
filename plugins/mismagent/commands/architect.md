---
description: Invoke mismAgent's architect (model movement) — dispatches the mismagent-architect subagent: two-pass headless DISCOVERY (stack + architecture style + infra deliberated WITH you) then writes architecture + ADRs and finalizes the profile gate. Use in model after the tactical model.
argument-hint: "[feature]"
---

Dispatch the **`mismagent-architect`** subagent (Agent tool) for `$ARGUMENTS` (or the current feature),
with the model inputs (prd/brief, `context-map.md`, the per-side guides, existing `architetture/*`).
**Two-pass pattern (it is headless):** pass-1 returns `STACK_PROPOSAL` / `ARCH_PROPOSAL` /
`INFRA_QUESTIONS` — bring those to me to decide, then re-dispatch pass-2 to write the
ADRs/architecture and finalize the profile `gate`. See `agents/mismagent-architect.md`.
