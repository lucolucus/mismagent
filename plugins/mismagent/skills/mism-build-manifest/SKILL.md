---
name: mism-build-manifest
description: mismAgent model movement (successor of mism-build-dag for the architecture-driven build). EMITS the building-block manifest (building-blocks.yaml) — the IDEA-2→build bridge that the Composer reads — as a CONSEQUENCE of the tactical model: aggregates→aggregate block, commands→application-service, Customer/Supplier relationship→port+adapter+boundary, events/views→read-model, screens→ui. Pins the TYPES at the boundaries (Published Language), picks the projection (in-process/cross-deploy) from the profile, attaches the user's tests_nl and the §14 gates. Replaces the file-task dag.yaml. Use after the architecture, before the Composer.
---

# mism-build-manifest — the IDEA-2 → build bridge

Emits `<output_dir>/<feature>/building-blocks.yaml`: the **Composer's only input**. The manifest is
a **consequence of the model** (anti-zombie: every row has a consumer = the Composer), not
hand-written. Rationale: `redesign/composer-spec.md` §8.

## Input
- `context-map.md` — tactical model (aggregates/invariants/commands/events) + Customer/Supplier relationships;
- `architetture/` + ADRs (including the §14 `enforced_by`);
- the **active profile** (`<output_dir>/profile.md`, default `.mismagent/profile.md`) —
  sides (→ projection), gate, identity/stack.

## Tactical → block map (§8.1)
| source in the model | → manifest row |
|----------------------|---------------------|
| aggregate + invariants | `aggregate` block (+ `invariants`, `invariant_fields`, `identity`, `tables`) |
| command(s) (per aggregate) | `application-service` block (`commands`, `consumes`) |
| **Customer/Supplier** relationship | `port` block (consumer-owned) + `adapter` + an inter `boundary` |
| domain event / view | `read-model` block (+ `view_shape`) |
| UI screen | `ui` block (`consumes_rm`, `triggers`) |

## Rules — each is also an item of the Composer's Phase 1 readiness
1. **PIN the types at the boundary = Published Language** (primitive or shared-kernel), **never** the
   supplier's domain type: pinning `ProductId` (from Catalog) on a Sales port would recreate
   Sales→Catalog. The `value class` lives **inside** the context; at the seam you speak primitives.
   *(Wave-1 lesson: an unpinned boundary ⇒ the workers, built blind, do not compose.)*
2. **projection** for every inter boundary: `in-process` if consumer and supplier are **the same side**
   (profile), otherwise `cross-deploy` (→ the port projects into OpenAPI + generated types + CDC; and
   the BE‖FE parallelism re-emerges as an *effect*, not dogma).
3. **contract_test**: `invariant-test` (aggregate boundary) · `consumer-driven` (port, read-model).
4. **§14 gate** for every aggregate boundary (from the `invariant_fields`/`tables`): no writes outside
   the adapter; the invariant field is **confined** → consumers use the **named predicate**.
5. **tests_nl (§16):** for every high-value block/boundary, **ask the user, in natural
   language, which tests they want** and attach them as `tests_nl` (the worker translates them into
   tests). A boundary **without** `tests_nl` is not ready: ask.
6. **build_order** derived: boundary owners first (aggregate, port), consumers in parallel.

## Output
`building-blocks.yaml` (blocks + boundaries with `projection` + `tests_nl` + gates + `build_order`).
Then the **Composer** reads it: its **Phase 1 (readiness)** re-verifies these rules before
building (pinned types, contract_test, projection, gates, tests_nl).

## Outcome
Summary: N blocks per type, M boundaries (with projection), confirmation of pinned types, `tests_nl`
elicited from the user, and what is missing before launching `/mismagent:composer`.
