---
description: Dispatch mismAgent's architect (model movement). Foundational (once per project, trunk missing) runs the two-pass deliberation with you; feature (trunk present) writes only this feature's boundary decisions. Use after the tactical model.
argument-hint: "[feature]"
---

**Decide the dispatch from the PROJECT trunk, never from the feature folder** (a new feature's
folder is empty by construction). Look at `<output_dir>/architecture.md`, `code-rules.md`,
`decisions/` and the profile's `gate`.

Model inputs for either dispatch: the feature's `product-brief.md` and
`features/<feature>/tactical-model.md`, the project's `context-map.md`, the per-side guides,
existing `architetture/*`.

- **Trunk absent** (`architecture.md` or `code-rules.md` missing, or `gate` still
  `manual — TBD after the stack ADR`) → dispatch the **`mismagent-architect`** subagent for
  `$ARGUMENTS` with `DISPATCH: foundational`. Pass 1 returns `STACK_PROPOSAL` / `ARCH_PROPOSAL` /
  `INFRA_QUESTIONS`: bring them to me to decide, then re-dispatch pass 2 to write the trunk and
  finalize the gate fields and the UI sides' `run` binding.
- **Trunk present** → dispatch with `DISPATCH: feature`, the trunk and the model inputs; no pass 1.
  Tell me what is fixed and by which ADR. A foundational decision is reopened only if I ask — then
  it is a superseding ADR plus the edit it implies, never a silent rewrite. Authoring the codebase's
  dev-architecture on a finalized trunk is a targeted dispatch, not a pass-1 re-run.

An artifact that already exists is stated, not re-deliberated (same rule as `/mismagent:model`).
See `agents/mismagent-architect.md`.
