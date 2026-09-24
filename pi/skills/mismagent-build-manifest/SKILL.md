---
name: mismagent-build-manifest
description: "mismAgent model movement. Derives building-blocks.yaml and its status-less block files from the tactical model \u2014 pinned boundaries, user tests_nl, releases, scaffold, spikes. Use after the architect, before the worker-composer."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# build-manifest — the model → build bridge

Emits `<output_dir>/features/<feature>/building-blocks.yaml` — the worker-composer's only input — and
seeds one derived block file per row in `blocks/<context>/todo/<id>.md`. The manifest is a
**consequence of the model**, never hand-written: every field has a reader.

**Before writing or regenerating, read `references/manifest-schema.md`** (in this skill's folder):
it is the normative shape of the YAML and of the block files, and the per-type standard each block
must meet. Do not emit from memory.

## Input
- `features/<feature>/tactical-model.md` (aggregates, invariants, commands, events);
  `<output_dir>/context-map.md` (canonical names, Customer/Supplier relationships, open spikes);
- `features/<feature>/UI/ux-proposal.md` when the feature has UI;
- `<output_dir>/architecture.md`, `architetture/`, the ADRs in `<output_dir>/decisions/`;
- the active profile (`<output_dir>/profile.md`): sides, gate, `run`,
  `ui_render_check`, **`capacity`** — wave width and block granularity are sized to the team.

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
   primitives or shared-kernel VOs, never the supplier's domain type.
2. **Pin recursively:** a composite type cited in a `pinned_types` row has its own row (or is a
   primitive / an already-pinned VO). Pin **every** event that crosses a boundary, not only those
   whose consumer is modeled yet.
3. **Keys:** for every id/correlation key, `keys:` pins who mints it, by what rule, and its stability
   (across versions, hot changes, republication). The pinned type carries **the key the consumer
   operates with**; a transport-only key with no pinned map to it is under-specified — fix it here.
   A string key minted or decoded by ≥ 2 contexts is a candidate for a shared-kernel VO.
4. **Granularity is a decision:** when a quantity crosses a seam and becomes units downstream, or
   enters a conserved invariant, unit-vs-quantity must already be decided in the model. Implicit →
   stop and ask (tactical-modeler or user).
5. **Reads come from preconditions too:** a command whose precondition reads another context's state
   is a boundary — project it into `consumes`.
6. **Every `view_shape` field has a source** — a consumed event's field, a boundary's
   `pinned_types`, or the write-path input. No source → refuse at generation. A read-model that
   supplies a boundary has `view_shape` ≡ that boundary's pinned type (one Published Language). Event
   fields are consumer-driven: derive them from the consuming folds; the types live once, in the
   shared kernel.
7. **Consumption guarantees:** a field someone orders by is pinned in an orderable format. A fold
   over > 1 writer stream for the same key needs single-writer-per-key **or** a commutative fold.
   Order, duplicates/replay and the fold rule live in the **Decision** of the boundary owner's ADR
   (the pack carries it to consumers); the fold's `tests_nl` cover the admitted permutations and
   duplicates. No declared guarantee → bounce to the architect, never assume order.
8. **`contract_test`:** `invariant-test` on an aggregate boundary, `consumer-driven` on port and
   read-model. A boundary an earlier feature introduced is reused, never redeclared.
9. **Confinement checks for every aggregate:** from `invariant_fields` and `tables` derive three
   constraints — persistent writes to its tables only in its adapter; state mutated only through the
   root; invariant fields read only inside the aggregate (consumers use the named predicate). Record
   each as a check reference on the aggregate's ADR, via `write-adr`:
   `enforced_by: [{check: <repo path>, from: <block-id>}]` — `from` only where the check can pass only
   once that block exists (a prohibition applies at once). A check targets packages/modules or
   symbols, never a guessed filename; the check file, its fixtures and its registration in the gate
   follow `write-adr`.

## Acceptance — tests_nl
10. For every high-value block and every boundary, **ask the user in natural language which tests
    they want** and attach them as `tests_nl`. A boundary without `tests_nl` is not ready: ask. Each
    item is **falsifiable on the block's real path**; one the slice satisfies by construction is
    reworded into a failable test or marked `by-construction` so nobody counts it as coverage. A `ui`
    block's `tests_nl` cover its states (empty/error/loading); rendering itself is proven by
    `realize-ui` and the side's `ui_render_check`.
11. **The invariant tag is a verifiable convention:** prescribe that each invariant test's name
    starts with `INV-n ` — no brackets, no character illegal in the stack's test names — so coverage
    is matched per block. Never turn it into a project-wide presence check (red for the whole wave).

## Structure — waves, owners, releases
12. **Waves:** the scaffold at `0`; owners (aggregate, port) before their consumers; consumers of a
    wave in parallel, width sized to `capacity`. Waves are integers — an extra wave is a renumbering.
13. **Scaffold (greenfield only):** a side whose gate cannot run yet gets one `type: scaffold` block,
    `wave: 0`, no boundary, no `tests_nl`; its acceptance is the side's gate green on the empty
    skeleton. It also wires the UI-test setup when `ui_render_check` is automated and satisfies the
    profile's `run` binding on a UI side.
    A project that already builds gets no scaffold.
14. **Shared artifact ⇒ derived owner block:** an artifact ≥ 2 blocks of the same wave consume (the
    shared-kernel types, a module's build files, a ui-kit, a schema/migration set, DI wiring) gets
    ONE owner block in an earlier wave, with no domain rules. Compute it from the manifest.
15. **Every prescribed capability names its owner module** (a local store, a sync engine, a ui-kit):
    in the block's module list, or stated in the spec.
16. **Group infrastructure by module:** the adapters of one infrastructure module are one block that
    `consumes` every boundary it implements. Split only for owners in different
    waves or different releases. Domain blocks keep one aggregate = one block.
17. **Every ux-prescribed surface lands or is declared cut:** each surface the ux-proposal assigns to
    a `ui` block has a `triggers`/`consumes_rm` entry, or a `notes` line saying where it went.
18. **`model_hint: deep`** on a consumer block only when it folds ≥ 2 boundaries, mints or re-keys a
    pinned key, depends on an ordering/commutativity guarantee, or was reshaped by an answered
    `open-questions/` file. Never for size alone.
19. **Releases:** every non-scaffold block has `release:`; `releases:` says what each lets the user
    do. **R0** is the thinnest launchable vertical slice (the app starts and does one real thing end
    to end) within the first 3 build waves after the scaffold — size it down until it fits. Present
    the R0 cut to the user at the `tests_nl` checkpoint.
20. **Central risks are wave-0 spikes:** every `central: true` spike of the context-map (and every
    risk the architect flagged) has a `type: spike` node with `central: true` — set the flag on the
    tactical-modeler's node, never emit a second one; only a risk with no node gets one, via
    `write-task`.

## Coherence and regeneration
21. **Reconcile before emitting:** check your pins against profile, `architecture.md` and the ADRs.
    A contradiction is resolved **with the user** and the losing artifact amended in the same pass.
22. **Regeneration is incremental.** Re-running refreshes the YAML and the block files in place from
    the current model; elicited `tests_nl` stay; ask only about new or changed blocks; report the
    delta (added / changed / unchanged). With blocks in `doing/` or `done/`, the delta is the only
    legal mode: re-seed only the impacted files, list them, never rewrite an unimpacted file and
    never move a file between state folders. Hand-editing a block file is a divergence bug.
23. **Un-parking:** fold the user's answer to a parked block into its spec, record the answer and
    why in `features/<feature>/decisions.md` (format: `.agents/skills/mismagent-worker-composer/references/CLI.md`; decider: the user), then delete its
    `open-questions/<block-id>.md` — regeneration is what clears it. A non-obvious R0 cut or
    `tests_nl` choice is recorded the same way.

## Output
- `building-blocks.yaml` — authoritative; `boundaries:` stays a first-class section.
- the block files — its per-block projection, status-less (the folder is the state).
- no other task list: the human reads the blocks live with `/skill:mismagent-board` (read-only).

Close by running `MM lint <output_dir>/features/<feature>/` (`MM` = `python3 .agents/skills/mismagent-worker-composer/scripts/mismagent.py`):
it is blocking — fix every gap before reporting.

## Outcome
Blocks per type (and the scaffold), boundaries, the releases (R0's blocks and its
wave), the central spikes, pinned types confirmed, `tests_nl` elicited, the delta on a re-run, and
what is missing before `/skill:mismagent-worker-composer`.
