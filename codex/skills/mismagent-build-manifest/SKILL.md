---
name: mismagent-build-manifest
description: "mismAgent model movement (successor of mism-build-dag for the architecture-driven build). EMITS the building-block manifest (building-blocks.yaml) \u2014 the model\u2192build bridge that the worker-composer reads \u2014 as a CONSEQUENCE of the tactical model: aggregates\u2192aggregate block, commands\u2192application-service, Customer/Supplier relationship\u2192port+adapter+boundary, events/views\u2192read-model, screens\u2192ui. Pins the TYPES at the boundaries (Published Language), picks the projection (in-process/cross-deploy) from the profile, attaches the user's tests_nl and the \u00a714 gates. In greenfield it also emits a wave-0 scaffold block (the buildable skeleton owner). Besides the authoritative YAML it seeds the DERIVED, status-less rich block files (one self-contained <id>.md per block in blocks/<ctx>/todo/, no checkboxes) so opening a block shows the whole block; the human reads them live via the read-only $mismagent-board. Replaces the file-task dag.yaml. Use after the architecture, before the worker-composer."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# build-manifest — the model → build bridge

Emits `<output_dir>/features/<feature>/building-blocks.yaml`: the **worker-composer's only input**. The manifest is
a **consequence of the model** (anti-zombie: every row has a consumer = the worker-composer), not
hand-written. Rationale: `redesign/composer-spec.md` §8.

## Input
- `<output_dir>/features/<feature>/tactical-model.md` — the tactical model
  (aggregates/invariants/commands/events); `<output_dir>/context-map.md` — the canonical names +
  Customer/Supplier relationships;
- `UI/ux-proposal.md` (if the feature has UI) — the screens/surfaces its `ui` blocks must land (rule 9);
- `<output_dir>/architecture.md` (the project module map) + `architetture/` + ADRs (including the
  §14 `enforced_by`);
- the **active profile** (`<output_dir>/profile.md`, default `.mismagent/profile.md`) —
  sides (→ projection), gate, identity/stack, **`capacity`** (who builds, with how many hours —
  wave width and block granularity are sized to the TEAM, not to the idealized problem;
  friction-log-4 #10).

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
   (profile), otherwise `cross-deploy` → the port projects into the **declared contract form**
   (`contract_form`, from the profile/ADR): request/response → **OpenAPI** + generated types + CDC;
   a replication/sync wire → a **versioned event-schema** (e.g. proto + event catalogue, additive
   evolution) + CDC on the events (friction-log-4 #5/#16). The BE‖FE parallelism re-emerges as an
   *effect*, not dogma.
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
   boundary owners (aggregate, port); then the consumers in parallel (width sized to the profile's
   `capacity`).
7. **scaffold block (greenfield only) — wave 0.** If the side has **no buildable project yet** (the
   profile's `gate` cannot even run: no wrapper / no module / no `src` tree), emit **one `scaffold`
   block per such side** with `wave: 0`, `type: scaffold`, no boundary, no `tests_nl`. Its acceptance
   is the negative space: **the side's `gate` runs GREEN on the empty skeleton**. The worker-composer
   builds it **before** every owner block (its `realize-scaffold` skill creates wrapper + module
   structure + plugins + sourceSets per the stack ADR / infra-notes). If the side renders UI and its
   `ui_render_check` (profile) is an **automated** check, the scaffold also wires the **UI-test
   dependency/config**, so the gate can execute the render proof from wave 0. If the side renders UI,
   the scaffold also **honors the profile's `run` binding** (the launch task/entry + port the
   profile pins *a priori* — the command must work on the empty skeleton; friction-log-4 #15). If a
   cross-deploy boundary declares `contract_form: event-schema` whose `schema_paths` live in this
   side's tree, the scaffold **creates that contract location** (the files are its output — Phase 1
   defers their check, friction-log-4 #16). Without the scaffold, in greenfield the
   owner blocks have nothing to compile against. *(If the project already builds, emit no scaffold.)*
8. **Re-entrant by regeneration — INCREMENTAL once the build is running** (friction-log-4 #14/#28):
   re-running refreshes the YAML + the derived block files **in place** from the current model — it
   is never a re-deliberation. `tests_nl` already elicited **stay**; ask the user only for **new or
   changed** blocks/boundaries, and report the delta (added/changed/unchanged) so a re-run is
   reviewable. **With blocks already in `doing/`/`done/` the delta mode is the ONLY legal one:**
   apply the change (a re-pinned boundary, a new owner block) to the YAML and re-seed **only the
   impacted derived files** — never move a file between state folders (state is the
   worker-composer's), never rewrite the files of unimpacted blocks, and list which files the delta
   touched. A full regeneration that resets state or others' refinements is a bug; doing the delta
   by hand outside this skill is exactly the manifest↔blocks divergence it exists to prevent.
9. **Every ux-prescribed surface lands or is declared cut** (friction-log-4 #11): for each `ui`
   block, check the ux-proposal's prescriptions against the manifest — every screen
   surface/interaction it assigns to the block has a matching `triggers`/`consumes_rm` entry, **or**
   an explicit cut (a `notes`/deferred line naming where it went — e.g. "writes node config, not
   the versioned aggregate"). Never leave a surface implicit: ambiguity discovered at seeding time
   is a model bug, not a worker's judgment call.
10. **Every prescribed capability names its OWNER module** (friction-log-4 #20): if a spec
    prescribes a concern (a local store, a sync engine, a ui-kit), the module that owns it must be
    in the block's module list — or the spec says explicitly where it lives. A capability with no
    named owner forces the worker to invent architecture; at wave 0 (`dev_architecture` inevitably
    absent) that invention becomes the precedent the harvest later canonizes.
11. **Shared artifact ⇒ DERIVED owner block** (friction-log-4 #25/#32): whenever an artifact is
    consumed by **≥2 blocks of the same wave** — the shared-kernel types the `pinned_types` name,
    the build/structure files of a module several blocks touch, a ui-kit (the design system's code
    incarnation) — emit ONE owner block for it, built before the wave (an intermediate "wave 0.5"
    is fine; no domain rules in it). Without an owner, N parallel workers write N divergent bodies
    of the same file and the wave's parallelism is illusory. This is a **derivation** you compute
    from the manifest (which types/files ≥2 same-wave blocks share), never a bespoke hand-fix.
12. **Pin RECURSIVELY** (friction-log-4 #29/#36): a composite type cited inside a `pinned_types`
    row (`biglietti:[BigliettoEmesso]`) must have its **own** `pinned_types` row — or be a
    primitive / an already-pinned shared-kernel VO. On an `event-schema` wire, pin **all** the
    events that cross it, not only those whose consumer is already modeled. A Published-Language
    type cited-but-undefined forces the worker to invent the Published Language — the one thing
    pinned boundaries exist to prevent.
13. **A key pins its MINTING RULE, its owner — and it is the CONSUMER'S key** (friction-log-4
    #34/#38/#41/#47): for every id/correlation key in a boundary's `pinned_types` or a
    producer-driven event payload, pin in the boundary's `keys:` **who mints it and by what rule**,
    including its **stability** (across catalogue versions / hot-changes / republications) — a bare
    `:string` makes N workers mint N incompatible rules, and a divergent correlation key breaks the
    domain downstream (the oversell class). The pinned type must carry **the key the consumer
    operates with**: if the consumer keys its state by X and the type carries only a
    transport/compact Y (a QR index) with no pinned Y→X map, the boundary is under-specified — fix
    it here, don't let the consumer invent a port. A string key minted/decoded by **≥2 contexts**
    is a candidate for a **typed shared-kernel VO** (one parse/format home) or for carrying the
    correlating fields explicitly instead of an opaque string.
14. **Seam granularity is a DECISION, never a worker default** (friction-log-4 #40): when an
    entity crossing a seam carries a quantity (`righe:[{qta}]`) that downstream becomes a count of
    units, and its identity is a correlation key or the quantity enters a **conserved invariant**
    (Porzioni), the unit-vs-quantity granularity is ubiquitous language: it must arrive here
    already decided (tactical model / user). FLAG any pinned type where it is implicit — two
    workers assuming different granularities merge blocks that are mutually incoherent, a latent
    seam mismatch that detonates only at the weld.
15. **Read boundaries derive from the model's PRECONDITIONS too** (friction-log-4 #42): a command
    whose precondition reads another context's state ("…and no item of the order is already
    delivered — reads the Monitor") IS a boundary: project it into `consumes` (a pinned read
    boundary, or an extension of an existing one). A cross-context read the context-map names but
    the manifest doesn't pin leaves the worker to invent a consumer-owned port on the spot.
16. **Every `view_shape` field has a SOURCE; a supplier's view_shape IS the pinned_type**
    (friction-log-4 #44/#45/#48): lint each `view_shape` field against a declared source — a field
    of an event the block `consumes`, a boundary's `pinned_types`, or the write-path input. No
    source → **refuse at generation** (the same gap surfaces later and dearer as a readiness or
    build bounce). A read-model that is the **supplier** of a boundary must have `view_shape` ≡
    the boundary's `pinned_type` (they are ONE Published Language written twice; two copies
    diverge). On a sync wire the events' fields are **consumer-driven** like any read: derive them
    from the folds the consuming read-models declare, and materialize the JVM event types in the
    shared kernel **together with** the schema forms (one PL, not two that diverge).
17. **Consumption-shaped guarantees: ordering and commutativity** (friction-log-4 #46/#50): a
    field a read-model/UI **orders by** requires the producer to pin an **orderable format**
    (fixed-width zero-pad, or a dedicated Comparable + the cross-namespace rule) — a lexicographic
    sort on an unpinned string is wrong at every digit boundary. A read-model folding events of
    **>1 writer stream for the same key**, over a wire that guarantees order only per-stream, is
    mechanically at risk under cross-node reordering: require **single-writer-per-key** (absolute
    values from the owning authority) OR a **declaredly commutative fold** (tombstones / orphan
    buffer) — and pin the wire's **`delivery:` guarantee** on the boundary (e.g. per-node in-order
    + dedup(nodeId, seq) BEFORE the fold) so consumers design against it and the sync adapter
    owes it.
18. **The invariant tag is PRESCRIBED, greppable and JVM-safe** (friction-log-4 #24): the
    manifest's `[INV-n]` form does not compile as a JVM test name (`[ ] . ; : / < >` are illegal
    even in Kotlin backticks). Prescribe the convention the workers use: the test **name starts
    with the tag `INV-n `** (no brackets). The verifier greps it per-block — never a global
    presence `enforced_by` (it would be red for the whole wave; friction-log-4 #19).
19. **Reconcile the manifest with profile · architecture · ADRs BEFORE emitting** (friction-log-4
    #22): grep your own pins against the other authoritative artifacts — a pin that contradicts a
    profile boundary rule ("VO at the seam" vs primitives pinned), an architecture-overview line,
    or an ADR (a boundary pinned as a COMMAND where the model says FACT, implying a dependency
    arrow the map forbids) is resolved **with the user** and the losing artifact amended in the
    same pass. Two authoritative artifacts that disagree in silence are two sources of truth;
    nothing downstream re-aligns them (methodology rule 7 applied to yourself).

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
       contract_form: openapi | event-schema       # cross-deploy ONLY — the FORM the contract takes
                                                   # (profile/ADR): request/response → openapi;
                                                   # replication/sync wire → event-schema (versioned,
                                                   # additive evolution)
       pinned_types: { <Name>: <primitive or shared-kernel VO>… }   # rule 1, Published Language
                                           # composite types cited here have their OWN row (rule 12)
       keys: { <field>: "minted by <block-id> — <rule + stability>" }  # rule 13 — every id/
                                           # correlation key: who mints it, how, across what it
                                           # stays stable (versions/hot-change/republication)
       contract_test: invariant-test | consumer-driven              # rule 3
       operation_ids: [<operationId>…]     # contract_form: openapi ONLY — each must resolve in the OpenAPI
       schema_paths: [<path>…]             # contract_form: event-schema ONLY — the versioned schema
                                           # files (proto/event catalogue); may be a wave-0 scaffold
                                           # OUTPUT (Phase 1 defers their check until the first
                                           # consuming block is ready)
       delivery: "<guarantee>"             # contract_form: event-schema ONLY — the wire's delivery
                                           # guarantee consumers design their folds against
                                           # (rule 17), e.g. "per-node in-order +
                                           # dedup(nodeId,seq) before the fold"
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
   The ADR set a block must read is **derived from the manifest** — its `related_adrs` ∪ those of
   the boundaries it consumes — **never a hand-compiled list in a prompt** (a hand list diverges
   from the manifest silently; friction-log-4 #12).
   **No `status:` field, no `[ ]` checkboxes** — the block's state **is its folder** (`todo/doing/done`),
   moved only by the worker-composer; the file's *content* is derived (re-running `build-manifest`
   refreshes content **in place**, it never moves files). Re-running is also how a **parked bounce
   un-parks**: fold the user's answer into the spec (`tests_nl`/criteria) and **delete that block's
   `<output_dir>/features/<feature>/open-questions/<block-id>.md`** — the worker-composer wrote it when the
   worker bounced, and regeneration is what clears it. The YAML stays the source of truth; these
   files are its **per-block projection** (the way OpenAPI is the cross-deploy projection of a boundary).
   No static `TASKS.md` — the rich block files + the board (below) replace it.

   ### The block-spec standard — completeness is LINTED, not judged
   The file is derived, so richness costs nothing: hold every block to this per-type standard.
   You enforce it at generation; the **worker-composer's Phase 1 re-checks it** (a gap ⇒ the block
   is **not ready**, gap named, BOUNCE back here — regenerate, never hand-patch the file):
   - **every block:** `## What to do` non-empty; `## Tasks` ≥ 1 criterion; a closing `Sources:`
     line pointing at the `related_adrs` + the tactical-model section it derives from;
   - **aggregate:** every frontmatter `invariants` item is spelled out in the body AND covered by
     ≥ 1 `## Tasks` criterion (an invariant nobody tests is a wish, not an invariant);
   - **application-service:** every `commands` item has ≥ 1 happy-path criterion AND ≥ 1
     rejection/failure criterion;
   - **port / adapter — and ANY block at a boundary:** every boundary the block touches appears in
     `## Dependencies` with the **pinned signature inlined** (the Published-Language types + the
     `contract_test` name, **plus the boundary's `keys:` minting rules and — on a sync wire — its
     `delivery:` guarantee**: the worker who mints a key or designs a fold must not open the YAML
     to learn them) — the reader must not open another file to know the seam;
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
