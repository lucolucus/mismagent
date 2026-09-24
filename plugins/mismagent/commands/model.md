---
description: mismAgent model movement as one command — conducts tactical-modeler → ux-designer → architect → build-manifest, stopping only at the human checkpoints. Writes only decision notes; resumes at the first missing artifact.
argument-hint: "[feature | <output_dir>/features/<feature>/]"
---

# Model — conductor of the model movement

You **sequence and stop at the checkpoints**; the agents and skills write every artifact. You write
none except one: each checkpoint's non-obvious choice as an entry of the feature's `decisions.md`
(format: `$CLAUDE_PLUGIN_ROOT/tools/CLI.md`; `python3 "$CLAUDE_PLUGIN_ROOT/tools/mismagent.py" why check <file>`).
You add no gate of your own (the model→build gate is the worker-composer's readiness). The single
commands stay equivalent step by step.

## 0 · Ingest
Resolve `<output_dir>/features/<feature>/` and the active profile (default `.mismagent/profile.md`).
Require the explore gate: the feature's `product-brief.md` and a project `<output_dir>/context-map.md`
covering the contexts this feature touches. Missing → stop: finish `/mismagent:explore` first.

## Steps — resume at the first missing artifact
Each signal is read at the scope of the artifact it guards: feature signals in
`features/<feature>/`, project signals in the `<output_dir>` root. An empty feature folder never
means the trunk is missing.

1. **Tactical** *(feature: no tactical-model sections, or seeds not absorbed)* — dispatch
   `mismagent-tactical-modeler`. `NEEDS-INPUT` → **checkpoint**: bring the `AMBIGUITIES` to the user,
   re-dispatch with the answers.
2. **UX** *(feature has UI, no `UI/ux-proposal.md`)* — the `ux-designer` skill, in dialogue with the
   user. No UI → skip and say so.
3. **Architect** *(project)* — choose the dispatch from the **trunk**:
   - `architecture.md` or `code-rules.md` missing, or the profile's gate still
     `manual — TBD after the stack ADR` → dispatch `mismagent-architect` with
     `DISPATCH: foundational`. Pass 1 returns `STACK_PROPOSAL`, `ARCH_PROPOSAL`, `INFRA_QUESTIONS` →
     **checkpoint: the user chooses**, even when one option looks obvious → pass 2 writes the trunk,
     the gate fields and the UI sides' `run` binding. On greenfield it also authors the codebase's
     dev-architecture before the first domain wave.
   - trunk present → `DISPATCH: feature` with the trunk and the model inputs (brief, tactical model,
     context-map, per-side guides, `architetture/`). Tell the user what is already fixed and by which
     ADR; reopen a foundational decision only if they ask — then it is a superseding ADR.
4. **Manifest** *(feature: no `building-blocks.yaml`, or the model changed)* — the `build-manifest`
   skill. **Checkpoint:** it elicits the `tests_nl` and the R0 cut from the user. Point the user at
   `/mismagent:board`. It closes with `python3 "$CLAUDE_PLUGIN_ROOT/tools/mismagent.py" lint <output_dir>/features/<feature>/`,
   the **blocking** check: zero gaps.

An artifact that already exists is stated and reopened only on request, never re-deliberated —
the single commands share this guard.

## 5 · Handoff
Optionally preview readiness with `readiness-gate`. Report the artifacts (paths), the decisions
deliberated with the user, open spikes and ambiguities, and the next command:
`/mismagent:worker-composer <feature>`.

## Invariants
1. You write no artifact but the decision notes; every handoff is a file (feature files in the
   feature folder, trunk files in the `<output_dir>` root), so the movement can span sessions.
2. You never skip a checkpoint and add no gate.
3. The trunk is decided once per project and changed only by an amendment the user asked for.
4. In a read-only harness only pass 1 and the checkpoints run; materialize the pending files as the
   first action once writes reopen.
