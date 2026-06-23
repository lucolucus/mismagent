---
name: build-manifest
description: mismAgent model movement (successor of mism-build-dag for the architecture-driven build). EMITS the building-block manifest (building-blocks.yaml) — the IDEA-2→build bridge that the worker-composer reads — as a CONSEQUENCE of the tactical model: aggregates→aggregate block, commands→application-service, Customer/Supplier relationship→port+adapter+boundary, events/views→read-model, screens→ui. Pins the TYPES at the boundaries (Published Language), picks the projection (in-process/cross-deploy) from the profile, attaches the user's tests_nl and the §14 gates. In greenfield it also emits a wave-0 scaffold block (the buildable skeleton owner). Besides the authoritative YAML it seeds the DERIVED, status-less rich block files (one self-contained <id>.md per block in blocks/<ctx>/todo/, no checkboxes) so opening a block shows the whole block; the human reads them live via the read-only /mismagent:board. Replaces the file-task dag.yaml. Use after the architecture, before the worker-composer.
---

# build-manifest — the IDEA-2 → build bridge

Emits `<output_dir>/<feature>/building-blocks.yaml`: the **worker-composer's only input**. The manifest is
a **consequence of the model** (anti-zombie: every row has a consumer = the worker-composer), not
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
| UI screen | `ui` block (`consumes_rm`, `triggers`); its `tests_nl` cover the screen's **states** (empty/error/loading) too — the worker tests them on the presenter, and `realize-ui` + the side's `ui_render_check` prove the rendering |

## Rules — each is also an item of the worker-composer's Phase 1 readiness
1. **PIN the types at the boundary = Published Language** (primitive or shared-kernel), **never** the
   supplier's domain type: pinning `ProductId` (from Catalog) on a Sales port would recreate
   Sales→Catalog. The `value class` lives **inside** the context; at the seam you speak primitives.
   *(Wave-1 lesson: an unpinned boundary ⇒ the workers, built blind, do not compose.)*
2. **projection** for every inter boundary: `in-process` if consumer and supplier are **the same side**
   (profile), otherwise `cross-deploy` (→ the port projects into OpenAPI + generated types + CDC; and
   the BE‖FE parallelism re-emerges as an *effect*, not dogma).
3. **contract_test**: `invariant-test` (aggregate boundary) · `consumer-driven` (port, read-model).
4. **§14 gate** for every aggregate boundary (from the `invariant_fields`/`tables`): no writes outside
   the adapter; the invariant field is **confined** → consumers use the **named predicate**. The
   generated greps are **code-scoped** (imports/field-access, not prose) and target the
   **package/dir or symbols**, never a guessed filename (#11/#12 — see §14).
5. **tests_nl (§16):** for every high-value block/boundary, **ask the user, in natural
   language, which tests they want** and attach them as `tests_nl` (the worker translates them into
   tests). A boundary **without** `tests_nl` is not ready: ask. For a **`ui` block** the `tests_nl`
   must include the screen's **states** (empty/error/loading); the **rendering** itself (sizing/
   overflow/contrast) is not a `tests_nl` item — it is owned by `realize-ui` + the side's
   `ui_render_check` (profile).
6. **build_order** derived: the wave-0 `scaffold` block (rule 7) precedes **all** owners; then the
   boundary owners (aggregate, port); then the consumers in parallel.
7. **scaffold block (greenfield only) — wave 0.** If the side has **no buildable project yet** (the
   profile's `gate` cannot even run: no wrapper / no module / no `src` tree), emit **one `scaffold`
   block per such side** with `wave: 0`, `type: scaffold`, no boundary, no `tests_nl`. Its acceptance
   is the negative space: **the side's `gate` runs GREEN on the empty skeleton**. The worker-composer
   builds it **before** every owner block (its `realize-scaffold` skill creates wrapper + module
   structure + plugins + sourceSets per the stack ADR / infra-notes). Without it, in greenfield the
   owner blocks have nothing to compile against. *(If the project already builds, emit no scaffold.)*

## Output
1. `building-blocks.yaml` — the **authoritative** source (blocks + the `boundaries:` section with
   `projection` + `tests_nl` + gates + `build_order` + any wave-0 `scaffold`). The **worker-composer's
   Phase 1** reads it (pinned types, contract_test, projection, gates, tests_nl). Keep the `boundaries:`
   as a first-class section (the architect's coherence + `create-contract`'s input depend on it).
2. **The rich block files** — a **DERIVED, status-less rendering** of the manifest, seeded one per
   block into `blocks/<context>/todo/<id>.md`, so opening a block shows the *whole* block (no more
   empty folder markers). Frontmatter mirrors the manifest row — `type`, `context`, `side`, `wave`,
   `consumes`, `related_adrs`, **+ per-type fields** (aggregate → `invariants`/`invariant_fields`/
   `tables`; port → `projection`/`pinned_types`/`contract_test`; read-model → `view_shape`). Body:
   ```
   # <id> — <title>
   ## Cosa fare      — what to build (from the model), 1–3 sentences
   ## Task           — the tests_nl/ACs as READ-ONLY acceptance criteria (plain list, NOT checkboxes)
   ## Dipendenze     — the boundary owners it waits on
   ```
   **No `status:` field, no `[ ]` checkboxes** — the block's state **is its folder** (`todo/doing/done`),
   moved only by the worker-composer; the file's *content* is derived (re-running `build-manifest`
   refreshes content **in place**, it never moves files). The YAML stays the source of truth; these
   files are its **per-block projection** (the way OpenAPI is the cross-deploy projection of a boundary).
   No static `TASKS.md` — the rich block files + the board (below) replace it.

## The live human view — the board (read-only)
The human reads the work via **`/mismagent:board [feature]`**: a read-only server that scans the block
files + their **folder position** (= block status) + (optionally) the **last test run** (per-AC
green/red) → a live kanban with each block's `## Cosa fare`/`## Task`. It **derives** progress, it
**never writes** the block files (no checkbox mutation) — coherent with "only the worker-composer moves
state". This is the visible surface that the hidden `.mismagent/.../blocks/` would otherwise bury.

## Outcome
Summary: N blocks per type (+ any wave-0 scaffold), M boundaries (with projection), confirmation of
pinned types, `tests_nl` elicited from the user, and what is missing before launching
`/mismagent:worker-composer`. Tell the user the block files are seeded in
`blocks/<context>/todo/` and that **`/mismagent:board`** shows them live.
