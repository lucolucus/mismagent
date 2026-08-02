---
name: mismagent-write-tactical-model
description: "mismAgent''s specialized tactical-model writer (explore\u2192model). Produces the PER-FEATURE file <output_dir>/features/<feature>/tactical-model.md: the \"Seeds for the tactical\" the analyst glimpses during the strategic (the explore\u2192model handoff), then the TACTICAL MODEL per context \u2014 aggregates, invariants, domain events, commands+actor \u2014 each row naming its downstream consumer. Lives with the feature and is thrown away with it; the PROJECT-level strategic map (bounded contexts + ubiquitous language) stays in <output_dir>/context-map.md (write-context-map). Invoked by mismagent-analyst (seeds) and mismagent-tactical-modeler (the model)."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# MismAgent — Write Tactical Model (writer, explore→model)

Write/update `<output_dir>/features/<feature>/tactical-model.md`. Invoked by `mismagent-analyst`
(the seeds, in explore) and by `mismagent-tactical-modeler` (the model, in model).
Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- **Aggregates / entities + invariants** → seed the manifest's **`aggregate` blocks** (with
  `invariants`/`invariant_fields`) and the **invariant ACs**; the `mismagent-verifier` demands a
  test for every invariant. Capturing them HERE prevents `model` from reinventing them (drift).
- **Domain events** → seed the **`read-model` blocks** (queries/views; the boundary projection
  decides whether they become GET endpoints) and the side-effects/guards of the writes.
- **Commands (+ actor)** → seed the **`application-service` blocks** (the projection decides
  whether they project into write endpoints with an `operationId`).

If an element has no consumer, **do not write it** — this holds row by row.

## Template
```markdown
# Tactical model — <feature>

> Strategic map (contexts, ubiquitous language, relationships): `<output_dir>/context-map.md`.
> The canonical names come from THERE — this file never renames them.

## Seeds for the tactical (to be consumed — the analyst writes, the tactical-modeler absorbs)
<!-- Aggregates/invariants GLIMPSED during the strategic. EPHEMERAL but PERSISTED section:
     it is the explore→model handoff. mismagent-tactical-modeler reads it from HERE (not from a
     message), absorbs it into "Tactical model" and then empties it. -->
- <glimpsed aggregate/invariant, 1 line each>

## Tactical model — <Context> — every row names the consumer, or it is not written
<!-- one section per bounded context THIS FEATURE touches; the context must already exist in the
     project context-map. A context the feature introduces is added THERE first (analyst). -->
- **Aggregates / entities:** <Aggregate (root)> guards <entities / value objects>
   → manifest `aggregate` block + architectural decision (architect)
- **Invariants:** [INV-1] <cross-field rule, e.g. extraordinary maintenance ⇒ requires an attachment>
   → acceptance criterion + invariant-test on the aggregate block (verified by mismagent-verifier)
- **Domain events:** <PastTenseEvent, e.g. MaintenanceRecorded>
   → `read-model` block (query/view) / side-effect / guard of the write
- **Commands (+ actor):** <Command, e.g. RecordMaintenance> (actor: <who expects it>)
   → `application-service` block; if the boundary projects cross-deploy, the operationId is born here
- **Policy:** <when X then Y>   → side-effect / downstream task  (omit if it has no consumer)
```

## Rules
- **Feature scope.** One file per feature, covering **only** the contexts that feature touches. It
  is not a domain library that grows across features: cross-feature prior art is the `git log` plus
  the project context-map.
- **The names are not yours.** Every term used here must already be canonical in
  `<output_dir>/context-map.md`. A concept with no canonical name yet is a gap for the **analyst**
  (amend the project map first), never a name you coin locally — that is exactly how the ubiquitous
  language drifts.
- **A context this feature introduces goes into the project map first**, then gets its tactical
  section here.
- Invariant ids (`INV-n`) are **local to the feature file** and referenced by the feature's blocks.

## Outcome
Path of the file, contexts covered, aggregates/invariants/events/commands written (each with its
consumer), seeds absorbed and emptied (if this was the tactical-modeler's pass), and any term that
had to be added to the project context-map to keep the language canonical.
