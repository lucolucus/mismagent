---
description: Invoke mismAgent's architect (model movement) — dispatches the mismagent-architect subagent: two-pass headless DISCOVERY (stack + architecture style + code-writing rules + infra deliberated WITH you) then writes architecture + ADRs + the project definition files (<output_dir>/architecture.md and code-rules.md) and finalizes the profile gate (incl. the dependency lint) and the UI sides' run binding. RE-ENTRANT — on a feature whose architecture is already finalized it says so and asks what to reopen, never re-deliberates. Use in model after the tactical model.
argument-hint: "[feature]"
---

**Re-entrance guard — BEFORE dispatching anything.** Read the feature's state: `decisions/` ADRs,
`architetture/architecture-overview.md`, the profile's `gate`. If the architecture is already
**finalized** (ADRs exist, gate no longer TBD), do **NOT** dispatch a fresh pass-1: a contextless
DISCOVERY would re-propose choices already deliberated — ignorant that some ADRs are the
*conclusions of an adverse review* (supersedes), not open questions — and make the user re-decide
decided things. Say what exists and ask: a **targeted re-opening** (name the decision/ADR to
revisit → dispatch with that scope + the existing ADRs as context) or a different feature. Same
resume rule as `/mismagent:model` — the single command is not exempt (friction-log-4 #14).

Otherwise dispatch the **`mismagent-architect`** subagent (Agent tool) for `$ARGUMENTS` (or the current feature),
with the model inputs (prd/brief, `context-map.md`, the per-side guides, existing `architetture/*`).
**Two-pass pattern (it is headless):** pass-1 returns `STACK_PROPOSAL` / `ARCH_PROPOSAL` (style +
quality drivers + the code-writing rules that follow) / `INFRA_QUESTIONS` — bring those to me to
decide, then re-dispatch pass-2 to write the ADRs/architecture, the project definition files
(`<output_dir>/architecture.md` + `code-rules.md`) and finalize the profile `gate` (incl. the
dependency lint) **and the UI sides' `run` binding**. See `agents/mismagent-architect.md`.
