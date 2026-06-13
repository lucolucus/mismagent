---
name: mism-build-dag
description: '⚠️ SUPERSEDED by mism-build-manifest (architecture-driven build: the model→build bridge is the building-block manifest, not a dag.yaml of file-tasks). Kept as a reference of the file-driven flow. — mismAgent model movement. Translates the DOMAIN MODEL (context-map: processes + bounded contexts) into per-side lean tasks (BE/FE/sync/infra): each process fans out into a BE-produces task + FE-consumes tasks, and the pairing declares the operationId from which mism-create-contract will reconcile the contract (the contract is a consequence, not a source). Plus dag.yaml (structure ONLY: depends_on edges + contract arcs) and the release tags.'
---

# MismAgent — Build DAG (model movement)

Transforms the **domain model** (`context-map.md`: processes + bounded contexts) +
`architetture/` into an **executable DAG** of tasks. The contract is **not an input**: it is a
*consequence* — the tasks declare the `operationId`s, `mism-create-contract` then reconciles them
into a single OpenAPI. Orientation: `methodology/mismagent.md`. You work in the parent `<output_dir>/<feature>/`.

## Input
- `context-map.md` — **the processes** (→ fan-out into tasks) + the domain's bounded contexts (from the
  profile) (→ slice boundaries) +
  the **ubiquitous language** (→ names of the `operationId`s) + the **tactical model** (commands →
  write BE produces tasks; domain events → read-model tasks; **invariants → invariant ACs**
  on the BE produces task) + the "Open spikes" section (→ DAG nodes).
- `architetture/*` (sharded with stable anchors), any existing `dag.yaml`.
- `infra-notes.md` (infra needs → `side: infra` tasks), if present.
- *(NOT the contract: it is a consequence of the tasks, produced afterwards by `mism-create-contract`.)*

## Output
1. **`<output_dir>/<feature>/dag.yaml`** — structure ONLY (see below).
2. **lean task-files** in `tasks/<side>/backlog/<slice>-<side>-<slug>.md` (target 80-120 lines).
3. (optional) `epics-N.md` as a **generated derived view**, never hand-written (or omitted).

## Vertical slice = release-tag (publishable increment)
A slice is what the user **sees** (value) = a **release-tag**: the tasks that compose it,
when all green and deployed, **turn on the feature-flag together**. It is NOT executable: it is
a parent node that fans out into per-side tasks. The slice's state is **derived** (green ⇔ all
`children` in `done/`), never written.

## Fan-out from the processes (the contract is born here, not the other way round)
Each **process** in `context-map.md` fans out into per-side tasks: whoever *serves* the data → **1
BE `produces` task**; whoever *uses* it (view/action) → **N FE `consumes` tasks**. The
produces/consumes pairing **declares an `operationId`** (name from the ubiquitous language): this is what
`mism-create-contract` will later reconcile into the YAML. For each BE `produces` task, generate the
recurring AC: *"a response-shape test on the endpoint's real JSON body exists"*.

## `dag.yaml` format (structure ONLY — NEVER state)
```yaml
# (e.g.) — illustrative slices/operationIds; the real sides come from the profile
slices:
  - id: slice-2-recording-viewable
    value: "Intervention recording viewable per machine"
    children: [2-1-be-post-create, 2-2-be-get-list, 1-3-fe-list-page]
edges:
  depends_on:
    - { from: 2-2-be-get-list, to: 1-2-be-migration-tables }   # cross-slice too
  contract:
    - { producer: 2-2-be-get-list, consumer: 1-3-fe-list-page, operationId: getMaintenanceByMachine }
```
The **nodes** are derived from the files in `tasks/**/` (filesystem is authoritative). `dag.yaml` declares
ONLY `slices.children` + `edges`. **No `status` in `dag.yaml`.**

## Lean task-file format (sharp boundary, silent on the "how")
```markdown
---
id: 2-2-be-get-maintenance-list        # (e.g.)
side: be                               # be | fe | sync | infra
repo: <repo of the `be` side — from the profile>
slice: slice-2-recording-viewable
depends_on: [1-2-be-migration-tables]
contract_ref:
  - operationId: getMaintenanceByMachine
    role: produces                     # produces | consumes
related_adrs: [0003-pagination-limit-1000]
references:                            # SECTION anchors, not whole files (budget §3)
  - architetture/<side-architecture-doc>#<anchor>   # e.g. data-model
  - <per-side-guide>#<section>   # e.g. the side's conventions
---
# Slice 2 / GET maintenance list per machine (BE)

## Acceptance Criteria (Gherkin)
Scenario: ...
  Given ... When ... Then ... And the body conforms to the contract's schema
Scenario: a response-shape test on the real JSON body exists   # BE produces tasks only

## References
- architetture/api/<feature>.openapi.yaml#operationId=getMaintenanceByMachine
```
**Forbidden in the task:** `status:`, `## Status`, `## File List`, `## Change Log`,
`## Dev Agent Record`, `## Dev Notes`, `## Implementation Plan`. State is the **folder**.
The worker derives the "how" from the sections pointed to in `references` + the side's dev-architecture skill (from the profile).

## Dependency rules
- `depends_on` and `contract_ref/role` are **lists** (an FE task can consume multiple operations).
- `depends_on` can be **cross-slice**. The slice→task hierarchy is about release, not
  dependency: dependencies live only in the `edges`.
- Keep each task within the **context budget** (≤ ~5 references, 80-120 lines). If it overflows →
  the slice is too big → **split it**.
- **ADDITIVE contract change on a read** (field added, backwards-compatible): do NOT
  add a BE→FE `depends_on`. The FE `consumes` task already has the **generated types** and can
  be developed **in parallel** with the BE; the order applies **only at deploy** (enforced by the
  `contract` arc + the orchestrator's sequencing gate, not `depends_on`). Add a BE→FE `depends_on`
  only for **non-additive/breaking** changes (the shape changes under the FE's feet).

## Procedure (the tasks are written by `mism-write-task`; you decide structure and edges)
1. Group the FRs into **vertical slices** of value (the boundaries follow the bounded contexts of the
   `context-map.md`); for each one write `value` + `children`.
2. **Spike ingestion:** for each entry of the "Open spikes" section of the `context-map.md` not
   yet resolved → create a **`type: spike`** node (via `mism-write-task`) and link via
   `depends_on` the tasks that depend on it (an open spike blocks them until it is closed).
3. From the **processes** of the `context-map.md` do the **fan-out**: for each one, 1 BE `produces` task + N
   FE `consumes` tasks, declaring the `operationId` (name from the ubiquitous language). **If the
   process is a write (command), attach the context's invariants** (context-map → Tactical
   model) **as invariant ACs on the BE produces task.** For a change to an **already existing**
   operation, apply the additive vs breaking rule (§Dependency rules) to decide
   whether to add a BE→FE `depends_on`.
4. **Infrastructure tasks:** for each need in `infra-notes.md` that maps to work → create a
   **`side: infra`** task (repo of the `infra` side, from the profile), without `contract_ref`.
5. Add the cross-cutting technical dependencies (migrations before endpoints; design-system
   before pages) as cross-slice `depends_on`.
6. Write the **lean** tasks with `mism-write-task` in `tasks/<side>/backlog/` (Gherkin ACs,
   anchor `references`, no state).
7. Write `dag.yaml` (slices + edges, no state).

## Outcome
Summary: slices created (value + children), N BE/FE tasks generated, `depends_on` and
`contract` edges added, tasks that overflowed the budget (to be split), and what is missing before the
readiness gate (`mism-readiness-gate`).
