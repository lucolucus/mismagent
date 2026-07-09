---
name: mismagent-build-manifest
description: "mismAgent model movement (successor of mism-build-dag for the architecture-driven build). EMITS the building-block manifest (building-blocks.yaml) \u2014 the model\u2192build bridge that the worker-composer reads \u2014 as a CONSEQUENCE of the tactical model: aggregates\u2192aggregate block, commands\u2192application-service, Customer/Supplier relationship\u2192port+adapter+boundary, events/views\u2192read-model, screens\u2192ui. Pins the TYPES at the boundaries (Published Language), picks the projection (in-process/cross-deploy) from the profile, attaches the user's tests_nl and the \u00a714 gates. In greenfield it also emits a wave-0 scaffold block (the buildable skeleton owner). Besides the authoritative YAML it seeds the DERIVED, status-less rich block files (one self-contained <id>.md per block in blocks/<ctx>/todo/, no checkboxes) so opening a block shows the whole block; the human reads them live via the read-only $mismagent-board. Replaces the file-task dag.yaml. Use after the architecture, before the worker-composer."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# build-manifest — the model → build bridge

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
   tests). A boundary **without** `tests_nl` is not ready: ask. Each item must be **falsifiable on
   the block's real path**: an AC the slice satisfies *by construction* (it cannot fail — e.g. "no
   future date" where the date is always `now`) proves nothing; rework it into a failable test or
   mark it `by-construction` so nobody counts it as coverage. For a **`ui` block** the `tests_nl`
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
   structure + plugins + sourceSets per the stack ADR / infra-notes). If the side renders UI and its
   `ui_render_check` (profile) is an **automated** check, the scaffold also wires the **UI-test
   dependency/config**, so the gate can execute the render proof from wave 0. Without it, in greenfield the
   owner blocks have nothing to compile against. *(If the project already builds, emit no scaffold.)*

## Output
1. `building-blocks.yaml` — the **authoritative** source (blocks + the `boundaries:` section with
   `projection` + `tests_nl` + gates + `build_order` + any wave-0 `scaffold`). The **worker-composer's
   Phase 1** reads it (pinned types, contract_test, projection, gates, tests_nl). Keep the `boundaries:`
   as a first-class section (the architect's coherence + `create-contract`'s input depend on it).

   ### The manifest's shape (NORMATIVE — Phase 1 reads exactly these fields)
   ```yaml
   blocks:
     - id: <slug>                  # unique
       type: aggregate | application-service | port | adapter | read-model | ui | scaffold
       context: <bounded-context>
       side: <side>                # from the profile
       wave: 0 | 1 | 2 …           # 0 ONLY for scaffold; otherwise derived (owners before consumers)
       consumes: [<boundary-id>…]  # boundaries this block consumes (empty for owners/scaffold)
       tests_nl: [<falsifiable AC in natural language>…]   # rule 5; `by-construction` marked as such
       related_adrs: [<NNNN>…]
       # per-type fields:
       invariants: [<INV-n rule>…]         # aggregate
       invariant_fields: [<field>…]        # aggregate (the §14 gates derive from these)
       identity: <id strategy>             # aggregate
       tables: [<table>…]                  # aggregate
       commands: [<Command>…]              # application-service
       view_shape: { <field>: <type>… }    # read-model
       consumes_rm: [<read-model id>…]     # ui
       triggers: [<Command>…]              # ui
   boundaries:                     # FIRST-CLASS section
     - id: <slug>
       owner: <block-id>           # aggregate | port — built before its consumers
       consumers: [<block-id>…]
       projection: in-process | cross-deploy       # rule 2 (from the profile's sides)
       pinned_types: { <Name>: <primitive or shared-kernel VO>… }   # rule 1, Published Language
       contract_test: invariant-test | consumer-driven              # rule 3
       operation_ids: [<operationId>…]     # cross-deploy ONLY — each must resolve in the OpenAPI
   build_order: [[<wave-0>…], [<owners>…], [<consumers>…]]          # derived, rule 6
   ```
   Anything a consumer needs that is not in this shape **does not exist**: extend THIS section
   first, then the readers (worker-composer Phase 1, the block files, the board).
2. **The rich block files** — a **DERIVED, status-less rendering** of the manifest, seeded one per
   block into `blocks/<context>/todo/<id>.md`, so opening a block shows the *whole* block (no more
   empty folder markers). Frontmatter mirrors the manifest row — `type`, `context`, `side`, `wave`,
   `consumes`, `related_adrs`, **+ per-type fields** (aggregate → `invariants`/`invariant_fields`/
   `tables`; port → `projection`/`pinned_types`/`contract_test`; read-model → `view_shape`). Body:
   ```
   # <id> — <title>
   ## What to do     — what to build (from the model), 1–3 sentences
   ## Tasks          — the tests_nl/ACs as READ-ONLY acceptance criteria (plain list, NOT checkboxes)
   ## Dependencies   — the boundary owners it waits on
   ```
   **No `status:` field, no `[ ]` checkboxes** — the block's state **is its folder** (`todo/doing/done`),
   moved only by the worker-composer; the file's *content* is derived (re-running `build-manifest`
   refreshes content **in place**, it never moves files). Re-running is also how a **parked bounce
   un-parks**: fold the user's answer into the spec (`tests_nl`/criteria) and **delete that block's
   `<output_dir>/<feature>/open-questions/<block-id>.md`** — the worker-composer wrote it when the
   worker bounced, and regeneration is what clears it. The YAML stays the source of truth; these
   files are its **per-block projection** (the way OpenAPI is the cross-deploy projection of a boundary).
   No static `TASKS.md` — the rich block files + the board (below) replace it.

   ### The block-spec standard — completeness is LINTED, not judged
   The file is derived, so richness costs nothing: hold every block to this per-type standard.
   You enforce it at generation; the **worker-composer's Phase 1 re-checks it** (a gap ⇒ the block
   is **not ready**, gap named, BOUNCE back here — regenerate, never hand-patch the file):
   - **every block:** `## What to do` non-empty; `## Tasks` ≥ 1 criterion; a closing `Sources:`
     line pointing at the `related_adrs` + the context-map section it derives from;
   - **aggregate:** every frontmatter `invariants` item is spelled out in the body AND covered by
     ≥ 1 `## Tasks` criterion (an invariant nobody tests is a wish, not an invariant);
   - **application-service:** every `commands` item has ≥ 1 happy-path criterion AND ≥ 1
     rejection/failure criterion;
   - **port / adapter:** every boundary the block touches appears in `## Dependencies` with the
     **pinned signature inlined** (the Published-Language types + the `contract_test` name) — the
     reader must not open another file to know the seam;
   - **read-model:** the `view_shape` fields are reflected in ≥ 1 criterion;
   - **ui:** the screen's states (empty/error/loading) are covered (rule 5).
   The lint is structural and mechanical: it governs the **floor** of detail a human can rely on
   when opening any block; the ceiling stays the user's `tests_nl`.

## The live human view — the board (read-only)
The human reads the work via **`$mismagent-board [feature]`**: a read-only server that scans the block
files + their **folder position** (= block status) + (optionally) the **last test run** (per-AC
green/red) → a live kanban with each block's `## What to do`/`## Tasks`. It **derives** progress, it
**never writes** the block files (no checkbox mutation) — coherent with "only the worker-composer moves
state". This is the visible surface that the hidden `.mismagent/.../blocks/` would otherwise bury.

## Outcome
Summary: N blocks per type (+ any wave-0 scaffold), M boundaries (with projection), confirmation of
pinned types, `tests_nl` elicited from the user, and what is missing before launching
`$mismagent-worker-composer`. Tell the user the block files are seeded in
`blocks/<context>/todo/` and that **`$mismagent-board`** shows them live.
