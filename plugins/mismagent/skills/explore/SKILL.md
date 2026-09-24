---
name: explore
description: 'mismAgent explore movement. In dialogue with the user, turns a raw idea into an understood problem: bootstraps the profile, runs challenger and analyst, writes the product brief and amends the context-map. Use at the start of a feature.'
---

# mismAgent — Explore

From raw idea to **understood problem** and **domain model**. No contract, no tasks, no code here.
Orientation: `methodology/mismagent.md`.

You dialogue with the user in session (high presence) and use two subagents as tools:
**`mismagent-challenger`** (fresh context, tries to demolish the idea) and **`mismagent-analyst`**
(models the strategic domain). Write only what a downstream step reads.

**A feature is a unit of delivery** (one manifest, one build), not a unit of analysis. Depth lives in
the tactical model, `research/`, the ADRs and the block files — when the user asks for "one feature
per context", probe which depth they want before cutting. Variability across instances (tenants,
seasons…) is modeled as language here; a generic engine with no second concrete instance is for the
challenger to attack.

## Output (each with its reader)
1. `features/<feature>/product-brief.md` — problem, user, value, scope, outcome → the gate to model.
2. `<output_dir>/context-map.md` — the **project** map (contexts, relationships, ubiquitous language,
   open spikes), written by the analyst via `write-context-map`; amended on later features, never
   re-forked.
3. `features/<feature>/tactical-model.md` — the "Seeds for the tactical" (the analyst, via
   `write-tactical-model`) → the tactical-modeler and build-manifest.
4. Spikes for the unknowns, listed in the context-map (materialized as nodes in model).
5. `<output_dir>/infra-notes.md` first draft, only if it does not exist (`write-infra-notes`).
6. `research/<topic>.md` when a decision needs investigation (`mismagent-researcher`).

## Procedure
0. **Profile — bootstrap only if missing.** On any later feature the profile and the whole trunk
   exist: read them, never re-bootstrap. If `<output_dir>/profile.md` is missing, create it from
   `PROFILE.md` with the bootstrap fields only: `output_dir` (default `.mismagent`),
   `ubiquitous_language.lang`, sides, **`validation_mode`**, **`materials`**,
   **`capacity`**. The last three must come from the user: if the dialogue does not surface them,
   **ask explicitly** (the profile's comments say why each matters).
   Never invent `gate` or `dev_architecture`: the architect finalizes them.
1. **Diverge** with the user: goals, users, constraints, alternatives.
2. **Attack before modeling:** dispatch `mismagent-challenger`. `KILL` → stop and report; `RESHAPE`
   → redesign with the user; `PROCEED` → close its `MUST_ANSWER_BEFORE_MODELING` items first.
   Record the challenger's debate and the user's non-obvious choice (a `KILL` too) in
   `features/<feature>/decisions.md` (format: `${CLAUDE_PLUGIN_ROOT}/tools/CLI.md`, scope `feature`;
   a choice a requirement or the scope decides takes the short form); `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mismagent.py" why check <file>`.
3. **Model:** dispatch `mismagent-analyst` on what survived, passing the existing context-map as
   authoritative when there is one (it amends: adds this feature's contexts and terms, reuses the
   rest verbatim). `NEEDS-INPUT` → bring the `AMBIGUITIES` to the user and re-dispatch. A needed
   rename goes to the user and becomes an ADR. A spike the user answers: you close it (`write-task`).
4. **Converge** on `product-brief.md`.
5. **Infra draft** only if `infra-notes.md` does not exist; afterwards only the architect amends it.
6. **Research on demand** via `mismagent-researcher`.

## Read-only harness (e.g. plan mode)
The dialogue continues and the challenger dispatches (it is read-only). Do **not** dispatch the
researcher or the analyst: their handoffs are files, and a return message would evaporate. List the
pending writes (decision notes included) in the plan as files to materialize; when writes reopen, materializing them is the
**first** action (profile → brief), then the analyst.

## Gate to model
`model` starts only when the feature's `product-brief.md` (problem, user, value) **and** the
project's `context-map.md` (at least the contexts this feature touches, with their language) exist
as files. Otherwise stay in explore.

## Outcome
Bounded contexts and key terms, the brief's problem/user/value, the challenger's verdict, open
spikes, research produced, and whether the gate to model holds.
