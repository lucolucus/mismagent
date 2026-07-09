---
name: mismagent-model
description: "mismAgent's model movement as ONE command (the build's worker-composer twin, for model). Thin CONDUCTOR \u2014 sequences mismagent-tactical-modeler \u2192 ux-designer (if UI) \u2192 mismagent-architect (two-pass) \u2192 build-manifest \u2192 create-contract (cross-deploy only), stopping ONLY at the three human checkpoints (NEEDS-INPUT ambiguities \u00b7 the stack/architecture/infra deliberation \u00b7 the tests_nl elicitation). Writes no artifact itself; every handoff stays a FILE; the five single commands remain invocable for the step-by-step form. Re-entrant: resumes at the first missing artifact."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# Model — conductor of mismAgent's *model* movement

You are a **THIN conductor**, the model-movement twin of the worker-composer: you **sequence and
stop at the checkpoints**; the agents/skills produce every artifact — you write **none** yourself,
and you add **no gate of your own** (the model→build gate stays the worker-composer's Phase 1).
The step-by-step form (`$mismagent-tactical-modeler`, …) remains equivalent: this command is the
same flow with the typing removed, not a new paradigm.

## 0 · INGEST
`<the argument this skill was invoked with>` = feature or path → resolve `<output_dir>/<feature>/` + the **active profile**
(default `.mismagent/profile.md`). Require the **explore gate**: `product-brief.md`
(problem/user/value/scope) **and** `context-map.md` (bounded contexts + ubiquitous language).
Missing → stop and say so: finish `$mismagent-explore` first (that gate is explore's, not yours).

## 1 · TACTICAL — dispatch `mismagent-tactical-modeler`
It absorbs the context-map's "Seeds for the tactical" → writes the "Tactical model" section and
materializes the spikes (`write-task`). `NEEDS-INPUT` → **CHECKPOINT: bring the `AMBIGUITIES` to
the user**, re-dispatch with the answers. `MODEL-READY` → go on.

## 2 · UX (only if the feature has UI) — `ux-designer` skill
Concept dialogued **with the user** → `UI/ux-proposal.md`. No UI → skip, say so.

## 3 · ARCHITECT — dispatch `mismagent-architect`, two-pass; the deliberation is the USER'S
- **Pass 1 — DISCOVERY** (it writes nothing): returns `STACK_PROPOSAL` + `ARCH_PROPOSAL` +
  `INFRA_QUESTIONS`.
- **CHECKPOINT: present them to the user — they choose.** Never skip this even when one option
  looks obvious: a foundational decision without the checkpoint is a **process defect** (silent
  ADR), whatever the choice.
- **Pass 2 — WRITE**: re-dispatch with the decisions → `architecture-overview.md` + ADRs +
  infra-notes; it **finalizes the profile's `gate`**.

## 4 · MANIFEST — `build-manifest` skill
Tactical model → `building-blocks.yaml` (the normative shape in its § "The manifest's shape") +
the rich block files in `blocks/<ctx>/todo/`. **CHECKPOINT: elicit the `tests_nl` from the user**
for the high-value blocks (falsifiable on the real path, or marked `by-construction`). Then point
the user at **`$mismagent-board`** (live, read-only).

## 5 · CONTRACT (only if ≥1 boundary is `cross-deploy`)
`$mismagent-create-contract` → ONE OpenAPI. Module not enabled but a boundary is
cross-deploy → report **BLOCKED** (enable the module), do **not** improvise the projection.
All boundaries in-process → this step **does not exist**.

## 6 · HANDOFF
Optionally preview readiness (`readiness-gate` — a thin pre-flight of the worker-composer's
Phase 1, the one authoritative gate). Report: artifacts produced (paths), decisions **deliberated
with the user**, open spikes/ambiguities, and the next command:
**`$mismagent-worker-composer <feature>`**.

## RE-ENTRANT by design
Every invocation re-reads the **files** and resumes at the **first missing artifact**: no
"Tactical model" section → §1 · UI feature with no `UI/ux-proposal.md` → §2 · no ADRs / `gate`
still TBD → §3 · no `building-blocks.yaml` → §4 · cross-deploy boundary with no OpenAPI → §5.
Handoffs are FILES (rule #4), so the movement can span sessions. In a **read-only/plan-mode
harness**: only the dialogue-and-propose parts run (pass-1, checkpoints); **materialize the
pending files as the FIRST action once writes reopen** — a plan's text is not a handoff.

## INVARIANTS you NEVER violate
1. You write **no artifact yourself** — the movement's agents/skills do (you conduct).
2. You **never skip a checkpoint**, and you add no extra gate (model→build is judged by the
   worker-composer's Phase 1 alone).
3. Every handoff you rely on is a **FILE** in `<output_dir>/<feature>/`, never a return message.
