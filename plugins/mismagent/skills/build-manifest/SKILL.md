---
name: build-manifest
description: mismAgent model movement. Derives building-blocks.yaml and its status-less block files from the tactical model — pinned boundaries, user tests_nl, releases, scaffold, spikes. Use after the architect, before the worker-composer.
---

# build-manifest — the model → build bridge

Emits `<output_dir>/features/<feature>/building-blocks.yaml`, the worker-composer's only input. You
author only the YAML; `MM manifest render F` (`MM` = `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mismagent.py"`,
`F` = the feature folder) renders one block file per row — never hand-patch one (a legacy manifest: rule 22). The
manifest is a **consequence of the model**: every field has a reader.

**First read `references/manifest-schema.md`** (this skill's folder): the normative YAML, block
files and per-type standard.

## Input
- `features/<feature>/tactical-model.md` (aggregates, invariants, commands, events);
  `<output_dir>/context-map.md` (canonical names, Customer/Supplier relationships, open spikes);
- `features/<feature>/UI/ux-proposal.md` when the feature has UI;
- `<output_dir>/architecture.md`, `architetture/`, the ADRs in `<output_dir>/decisions/`;
- the active profile (`<output_dir>/profile.md`): sides, gate, `run`,
  `ui_render_check`, **`capacity`** (sizes wave width and block granularity).

## Tactical → block map
| in the model | → manifest row |
|---|---|
| aggregate + invariants | `aggregate` (+ `invariants`, `invariant_fields`, `identity`, `tables`) |
| commands of an aggregate | `application-service` (`commands`, `consumes`) |
| Customer/Supplier relationship | consumer-owned `port` + `adapter` + a `boundary` |
| domain event / view | `read-model` (+ `view_shape`) |
| UI screen | `ui` (`consumes_rm`, `triggers`) |

## Boundaries — what crosses a seam is PINNED, never invented in parallel
1. **Pin the Published Language** under the context-map's canonical names: `pinned_types` are
   primitives or shared-kernel VOs, never the supplier's domain type. A limit, unit or id a consumer
   shows or validates comes from its owner through the boundary, never re-declared.
2. **Pin recursively:** a composite type cited in a `pinned_types` row has its own row (or is a
   primitive / an already-pinned VO). Pin **every** boundary-crossing event, even an unconsumed one.
3. **Keys:** for every id/correlation key, `keys:` pins who mints it, by what rule, and its stability
   (across versions, hot changes, republication). The pinned type carries **the key the consumer
   operates with**, never a transport-only key.
   A string key minted or decoded by ≥ 2 contexts is a candidate for a shared-kernel VO.
4. **Granularity is a decision:** a quantity crossing a seam into units downstream, or into a
   conserved invariant, has unit-vs-quantity decided in the model. Implicit → ask (tactical-modeler
   or user).
5. **Reads come from preconditions too:** a command whose precondition reads another context's state
   is a boundary — project it into `consumes`.
6. **Every `view_shape` field has a source**: a consumed event's field, a boundary's
   `pinned_types`, or the write-path input — else refuse. A read-model that
   supplies a boundary has `view_shape` ≡ that boundary's pinned type (one Published Language). Event
   fields are consumer-driven (derived from the consuming folds); their types live once, in the
   shared kernel.
7. **Consumption guarantees:** a field someone orders by is pinned in an orderable format. A fold
   over > 1 writer stream for the same key needs single-writer-per-key **or** a commutative fold.
   Order, duplicates/replay and the fold rule live in the boundary owner's ADR **Decision**; the
   fold's `tests_nl` cover its admitted permutations and duplicates. No declared guarantee → bounce to the architect, never assume order.
8. **`contract_test`:** `invariant-test` on an aggregate boundary, `consumer-driven` on port and
   read-model. A boundary an earlier feature introduced is reused, never redeclared.
9. **Confinement checks for every aggregate:** from `invariant_fields` and `tables` derive three
   constraints — persistent writes to its tables only in its adapter; state mutated only through the
   root; invariant fields read only inside the aggregate (consumers use the named predicate). Record
   each on the aggregate's ADR via `write-adr`:
   `enforced_by: [{check: <repo path>, from: <block-id>}]` — `from` only where the check can pass only
   once that block exists (a prohibition applies at once). A check targets packages/modules or
   symbols, never a guessed filename; its file, fixtures and gate registration follow `write-adr`.

## Acceptance — tests_nl
10. For every high-value block and boundary, **ask the user in natural language which tests
    they want**; attach them as `tests_nl`. A boundary without `tests_nl` is not ready: ask. Each
    item is **falsifiable on the block's real path**; one the slice satisfies by construction is
    reworded into a failable test or marked `by-construction` (not coverage). A `ui`
    block's `tests_nl` cover its states (empty/error/loading); rendering is proven by
    `realize-ui` and the side's `ui_render_check`.
11. **The invariant tag is a verifiable convention:** each invariant test's name carries its tag —
    canonical `INV-n` in the docs, spelled per the dev-architecture (e.g. `INV_12`),
    matched by number per block. Never a project-wide presence check (red for the whole wave).

## Structure — waves, owners, releases
12. **Waves:** the scaffold at `0`; boundary owners before their consumers; consumers of a
    wave in parallel. Other order → `after:` on the later block.
13. **Scaffold (greenfield only):** a side whose gate cannot run yet gets one `type: scaffold` block,
    `wave: 0`, no boundary, no `tests_nl`, **no domain** (no invariant, no shared type); its acceptance is the side's gate green on the empty
    skeleton. It also wires the UI-test setup when `ui_render_check` is automated and satisfies the
    profile's `run` binding on a UI side.
14. **Shared artifact ⇒ derived owner block** in an earlier wave:
    shared-kernel domain types (VOs, enums, their invariants) → a
    reviewed owner block; a technical artifact ≥ 2 blocks of a wave consume (a module's build
    files, a ui-kit, a schema/migration set) → one owner block, no domain rules. The **composition
    root** (the app's wiring; `composition_root:` in `architecture.md`) is extended in place only by
    each release's one `composition: true` block, `after:` its other blocks; they publish what it
    wires from their own dirs — a `ui` block, in `tests_nl`, the public entry points it is driven by
    (open, refresh, close).
15. **Every prescribed capability names its owner module** (a local store, a sync engine):
    in the block's module list, or stated in the spec.
16. **Group infrastructure by module:** the adapters of one infrastructure module are one block that
    `consumes` every boundary it implements, under its declared host context. Split only for owners
    in different waves or releases. Domain blocks keep one aggregate = one block.
17. **Every ux-prescribed surface lands or is declared cut:** each surface the ux-proposal assigns to
    a `ui` block has a `triggers`/`consumes_rm` entry, or a `notes` line saying where it went.
18. **`model_hint: deep`** on a consumer block only when it folds ≥ 2 boundaries, mints or re-keys a
    pinned key, depends on an ordering/commutativity guarantee, or was reshaped by an answered
    `open-questions/` file. Never for size alone.
19. **Releases:** every non-scaffold block has `release:`; `releases:` says what each lets the user
    do. **R0** is the thinnest launchable vertical slice (the app starts and does one real thing end
    to end), as few waves as the dependency graph allows — never bent to fit (domain in the
    scaffold, a boundary owned by the wrong block). Present the R0 cut to the user at the `tests_nl`
    checkpoint. A release is a point on the line (its tag), never a code layer: later releases extend
    the code in place **through blocks of their own** (`after:` the one they extend), never a note on
    a done block; no `tests_nl` asserts release history — a feature a user setting switches off
    stays testable behavior.
20. **Central risks are wave-0 spikes:** every `central: true` spike of the context-map (and every
    risk the architect flagged) has a `type: spike` node with `central: true`: flag the
    tactical-modeler's node, never emit a second; only a risk with no node gets one, via
    `write-task`. Fill each spike's `## Unblocks` with `- <block-id>` lines.

## Coherence and regeneration
21. **Reconcile before emitting:** check your pins against profile, `architecture.md` and the ADRs.
    A contradiction is resolved **with the user** and the losing artifact amended in the same pass.
22. **Regeneration is incremental.** Refresh the YAML from the current model, then
    `MM manifest render F` (keeps state folders, unchanged files); elicited `tests_nl` stay; ask
    only about new or changed blocks; report the delta. A **legacy**
    manifest (`MM lint` → `mode: legacy`) is never force-rendered: update the YAML and only the
    affected block files.
23. **Un-parking:** fold the user's answer into the parked block's spec (22), record answer and
    why in `features/<feature>/decisions.md` (format: `${CLAUDE_PLUGIN_ROOT}/tools/CLI.md`; decider: the user), then delete its
    `open-questions/<block-id>.md`. A non-obvious R0 cut or `tests_nl` choice is recorded the same way.

## Output
`building-blocks.yaml` (authoritative; `boundaries:` first-class) and the rendered, status-less
block files — no other task list.

Close with `MM manifest render F` (rendered mode only) then `MM lint F` (blocking): fix every YAML gap.

## Outcome
Blocks per type (scaffold included), boundaries, releases (R0's blocks and wave), central
spikes, pinned types, elicited `tests_nl`, the re-run delta, and what is missing before
`/mismagent:worker-composer`.
