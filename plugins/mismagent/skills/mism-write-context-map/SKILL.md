---
name: mism-write-context-map
description: 'mismAgent''s specialized context-map writer (explore movement). Produces <output_dir>/<feature>/context-map.md: bounded contexts (DDD strategic) + relationships + ubiquitous language per context + TACTICAL MODEL per context (aggregates/invariants/domain events/commands, each with its downstream consumer) + list of open spikes. Inspired by Agentheim''s Model/context-map, but with the tactical persisted per-feature. Invoked by mism-analyst (inside explore). Every element has a downstream consumer (survival test), so it is not a zombie.'
---

# MismAgent — Write Context Map (writer, explore)

Write/update `<output_dir>/<feature>/context-map.md`. Invoked by `mism-analyst`. Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- **Bounded contexts** → seed the **boundaries** (manifest boundaries, `mism-build-manifest`).
- **Ubiquitous language** → seeds the **canonical names** of blocks and types (and, if a boundary
  projects cross-deploy, of the OpenAPI `components/schemas`); the `mism-verifier` greps those
  terms on the diff → drift = FAIL.
- **Aggregates / entities + invariants** → seed the manifest's **`aggregate` blocks** (with
  `invariants`/`invariant_fields`) and the **invariant ACs**; the `mism-verifier` demands
  a test for every invariant. Capturing them HERE prevents `model` from reinventing them (drift).
- **Domain events** → seed the **`read-model` blocks** (queries/views; the boundary projection
  decides whether they become GET endpoints) and the side-effects/guards of the writes.
- **Commands (+ actor)** → seed the **`application-service` blocks** (the projection decides
  whether they project into write endpoints with an `operationId`).
- **Open spikes** → become **`type: spike` nodes** (via `mism-write-task`).

If an element has no consumer, **do not write it** — this holds row by row of the tactical model.

## Template
```markdown
# Context map — <feature>

## Bounded context: <Name>            <!-- from the profile; e.g. Maintenance (e.g.) -->
- **Role:** <core | supporting | generic> + <host of the view | upstream | downstream>
- **Ubiquitous language:** <Term = canonical values/meaning>   → schema name (verifier grep)

### Tactical model — every row names the consumer, or it is not written
- **Aggregates / entities:** <Aggregate (root)> guards <entities / value objects>
   → manifest `aggregate` block + architectural decision (architect)
- **Invariants:** [INV-1] <cross-field rule, e.g. extraordinary maintenance ⇒ requires an attachment>
   → Gherkin AC + invariant-test on the aggregate block (verified by mism-verifier)
- **Domain events:** <PastTenseEvent, e.g. MaintenanceRecorded>
   → `read-model` block (query/view) / side-effect / guard of the write
- **Commands (+ actor):** <Command, e.g. RecordMaintenance> (actor: <who expects it>)
   → `application-service` block; if the boundary projects cross-deploy, the operationId is born here
- **Policy:** <when X then Y>   → side-effect / downstream task  (omit if it has no consumer)

## Relationships
- <ContextA> → <ContextB> : <type: upstream/downstream, conformist, ACL...> — <note>

## Seeds for the tactical (to be consumed — the analyst writes, the tactical-modeler absorbs)
<!-- Aggregates/invariants GLIMPSED during the strategic. EPHEMERAL but PERSISTED section:
     it is the explore→model handoff (ex SEEDS_FOR_TACTICAL). mism-tactical-modeler reads it from
     HERE (not from a message), absorbs it into the "Tactical model" and then empties it. -->
- <glimpsed aggregate/invariant, 1 line each>

## Open spikes (unknowns/risks → future spike nodes)
- [ ] <spike-slug>: <question to answer> — <closure criterion> — expected side: <from the profile>
```

## Rules
- The ubiquitous-language terms are **canonical and in the domain language** — the language is
  declared by the profile (`ubiquitous_language.lang`); default: the language the domain speaks
  (e.g. an Italian-domain project keeps `TipoIntervento`, `StatoOcr`). They will become schema/type names:
  no scattered synonyms, **never** translate a term the domain already uses.
- Reuse the **domain's bounded contexts declared in the profile** as reference (e.g. a
  context like `Maintenance` (e.g.)).
- **Per-feature scope:** the file lives with the feature and covers only the contexts it touches.
  It is NOT a domain library that grows across features (explicit choice): cross-feature prior-art
  remains the `git log`. If a context is already modeled elsewhere, re-cite its canonical names
  for consistency, do **not** duplicate the model.
- Spikes are **actionable** (question + closure criterion), not vague notes.

## Outcome
Path of the file, bounded contexts written, key ubiquitous-language terms, invariants
captured (→ ACs / invariant-tests), Seeds for the tactical persisted, open spikes (materializable
as `type: spike` nodes via `mism-write-task`).
