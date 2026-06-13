# mismAgent — Development methodology with executable contract on folder-as-state

> **Final version (post adversarial critique).** Self-contained document.
> Lives in `_bmad-output/methodology/mism-dag.md`.
> Single source of truth of the methodology: if a sub-repo or another doc conflicts, this file wins.

---

## 0. Thesis in one line

A **vertical slice** is a parent node of the DAG that fans out into **per-side lean tasks** (BE, FE, sync, infra). The **STATE of each task IS the folder** the file lives in (`backlog/ todo/ doing/ done/`); the **slice's state is DERIVED** from its children; the **contract** is an **executable OpenAPI YAML** (single source, `produces`/`consumes` arc of the DAG, referenced by stable `operationId`), green only if its contract tests pass on BE **and** FE. **"Done" = that cut of the DAG is green and deployed in the two repos**, never "sprint closed".

The ten agreed principles (no-sprint, vertical-in-planning/horizontal-in-execution, state-in-one-place-only, BMad-head/pruned-tail, shared-executable-contract, lean-task, survival-test, BE‖FE-parallelism, specialized-agents-with-fresh-verification, full-pipeline) are the **binding rubric** of this document.

---

## 1. Iron invariants (violating them = a bug of the methodology)

1. **The task's state lives only in the folder.** No `status:` field in the frontmatter, no `## Status`/`## File List`/`## Change Log`/`## Dev Agent Record` section in the task's body. Transition = `git mv`, executed **only** by the orchestrator and the gate.
2. **The slice's state is never written.** It is computed on the fly: slice green ⇔ all its `children` are in `done/` and merged onto `master`.
3. **`dag.yaml` never contains state.** It contains ONLY structure: `depends_on` edges and `produces`/`consumes` contract arcs.
4. **The contract is one, YAML, executable.** Tasks POINT to it by `operationId`, they do not duplicate the schema. If it is not executable on both sides, it is a zombie and the gate BLOCKS.
5. **Workers do not touch the state.** They do not run `git mv`, do not write state, do not write `dag.yaml`. They only return a strict handoff.
6. **A single git-writer:** the orchestrator (`dev-orchestrator-v2`). It is the only one doing `git mv`, merge commits, and `dag.yaml` mutations.
7. **No time-based cadence.** No sprints, no `sprint-status.yaml`, no denormalized ledger, no double-state reconciliation.

### 1.1 Automatic enforcement of the invariants (CI, in both repos + parent)

Without enforcement, the engine reintroduces the ceremony "through the window". Mandatory CI hooks:

```bash
# guard-task-state.sh — fails the pipeline if a task reintroduces double-state
grep -rlE '^status:' _bmad-output/*/tasks/ && exit 1
grep -rlE '^## (Status|File List|Change Log|Dev Agent Record|Dev Notes|Implementation Plan)' \
     _bmad-output/*/tasks/ && exit 1
# guard-dag-nostate.sh — dag.yaml must not contain status
grep -nE '^\s*status:' _bmad-output/*/dag.yaml && exit 1
```

---

## 2. Lifecycle: idea → release

The phases are **sequential per artifact** but the **execution (PHASE-5) is parallel per-side**. Each phase has an explicit gate. "Done" is PHASE-7 for each cut of the DAG, not a calendar.

### PHASE-0 — Exploration, ideation & validation *(explicit opening gate)*
- **Purpose:** turn a raw idea into a **validated vision + strategic model of the bounded contexts** BEFORE PRD/contract/code (Agentheim's rule: *no premature coding*; it also avoids the upstream rigidity of contract-first). **No contract, no tasks in this phase.**
- **Double inspiration:** **BMad**'s product-brief (problem/user/value) + **Agentheim**'s Brainstorm/Model/Research (vision, context-map of the bounded contexts, ubiquitous language, spikes, research).
- **Opening gate:** `product-brief.md` (problem/user/value) **and** `context-map.md` (bounded contexts + ubiquitous language) exist; otherwise PHASE-1 does not start.
- **Input:** the user's idea; `sample/` (PDFs, machine-tool domain screenshots); `git log` of past features.
- **Output (each with a downstream consumer = passes the survival test):**
  - `product-brief.md` → consumed by the PHASE-1 gate;
  - `context-map.md` (bounded contexts + ubiquitous language) → the bounded contexts seed the **slice boundaries** (PHASE-3) and the ubiquitous language seeds the **canonical names of the contract's `components/schemas`** (PHASE-2), which `mism-verifier` greps (drift → FAIL);
  - **spikes** for the unknowns → they become **DAG nodes** (not lost prose);
  - (optional) `research/<topic>.md` → cited by the PHASE-2 **ADRs**.
  No state artifact. *No* Agentheim ubiquitous-language README / protocol.md without a consumer (they would be zombies).
- **Who:** SKILL **`mism-explore`** (generic engines on-demand: `bmad-brainstorming`/`bmad-domain-research`). Inline in main session with the user (human dialogue, no subagent).

### PHASE-1 — PRD *(product head)*
- **Purpose:** crystallize the functional boundary cross BE+FE with **numbered** FR/NFR. The only document the user reads for product decisions (Principle 4).
- **Input:** `product-brief.md`, `sample/`, `UI/` (e.g. `table-variant-A.html`) as the authoritative visual source.
- **Output:** `_bmad-output/<feature>/prd.md` (numbered FR/NFR), validated. **No hand-written FR→task coverage-map** (zombie): coverage is verified at the PHASE-3.5 gate.
- **Who:** `bmad-create-prd` → `bmad-validate-prd` (loop `bmad-edit-prd`) → `bmad-review-adversarial-general` on the PRD. Main session, the user in the loop.

### PHASE-2 — Architecture + executable CONTRACT (YAML) + ADRs
- **Purpose:** produce the single cross-side design and the BACKBONE: the API contract as **machine-readable** OpenAPI, not prose. Emit ADRs for the non-obvious choices.
- **Input:** `prd.md`, `UI/`, `be.md`/`fe.md`, existing `architetture/*`.
- **Authorship of the contract (see §7.1):** reads consumer-driven (the FE authors them), writes producer-driven (the BE/domain authors them); the architect arbitrates feasibility and coherence.
- **Output:**
  - `architetture/architecture-overview.md` (D-1..D-N table with rationale), `architecture-be-*.md`, `architecture-fe.md`;
  - **`architetture/api/<feature>.openapi.yaml` (the SINGLE source of the contract).** Every operation has a **stable `operationId`** and every domain enum/object is a **NAMED `components/schemas`** with the canonical domain name (e.g. `InterventionType`, not an anonymous name);
  - `api-backend-spec.md` **downgraded to pointers** (see §4.4.2): generated from the YAML, never hand-written;
  - `decisions/NNNN-<slug>.md` (ADRs; frontmatter `scope: global|be|fe`, `status`, `supersedes`, and — when the ADR imposes a mechanical constraint — an `enforced_by:` field with the executable grep/lint rule, see §4.5).
- **Sharding:** large architectures (>~15KB) are sharded with `bmad-shard-doc` into sections with **stable addressable anchors**, so the tasks' `references` point to a section, not a monolithic file (see §3 context budget).
- **Who:** SUBAGENT **`mism-architect`** (knows the meta-repo layout + the BE/FE golden rule; produces architecture + YAML + ADRs) using `bmad-create-architecture` as the engine; `bmad-testarch-framework` to pick the contract-test framework; `bmad-testarch-nfr` for the NFRs (e.g. NFR1 ≤1.5s). Review: `bmad-review-adversarial-general` + `bmad-review-edge-case-hunter` on the contract and the architecture.

### PHASE-2.5 — Contract infrastructure bootstrap *(one-time setup, red-phase)*
> The setup is one-time, but the **per-endpoint response-shape test is recurring work** (see PHASE-4 and §7). Here ONLY the one-time-setup is done.
- **Purpose:** make the contract an EXECUTABLE truth on BOTH sides (Principle 5). Closes the single-point-of-failure: without this phase the contract stays aspirational and drift rots (it already happened: FE `MaintenanceType` vs BE `InterventionType`).
- **Explicit and blocking deliverable of this phase: the worker's lean skill.** Create **`mism-dev-story-lean`** which (a) does NOT parse/write `Status`/`File List`/`Change Log`/`Dev Agent Record`, (b) emits the **strict return** as its sole output, (c) has a completion gate based on **green tests**, not on "Story Status set to review". Until this skill exists, invariant no. 1 is aspirational (the `bmad-dev-story` engine FORCES writing state — verified: `bmad-dev-story/checklist.md:8-9,52-54,60-61`). Also create the SUBAGENT `mism-developer-lean` consistent with the skill.
- **Output (one-time setup):**
  - **BE repo** (`machinecare-be`): `MachineCare.Integration.Tests/ContractTests.cs` which boots the API via `WebApplicationFactory`, fetches `/swagger/v1/swagger.json` (Swashbuckle already active: `MachineCare.Api/Program.cs:26 AddSwaggerGen`, `:101 UseSwagger`) and compares it structurally with the YAML. Command: `dotnet test --filter Contract`.
  - **FE repo** (`machinecare-fe`): npm `prebuild` script with `openapi-typescript` → `src/types/api.generated.ts` (replaces the drift-prone hand-written types); `contract.test.ts` which asserts that the endpoints in use exist in the YAML by `operationId`. Command: `npm run test:contract`.
  - **CI:** two independent pipelines (one per repo), contract test = **blocking** job; + the §1.1 guards.
  - Skill `mism-dev-story-lean` + agent `mism-developer-lean`.
- **Who:** `bmad-testarch-atdd` + `bmad-testarch-framework` (red-phase scaffold) + `bmad-testarch-ci` (pipelines); SUBAGENT `mism-developer-lean` implements the contract tests IN the correct repo (BE and FE separately, never crossing the boundary — golden rule AGENTS.md §3).

### PHASE-3 — DAG of vertical slices + ATDD scaffold
- **Purpose:** translate PRD+Arch+contract into a computable DAG (Principles 2,3). The ATDD scaffold materializes the ACs into red tests before the implementation.
- **Input:** `prd.md`, `architetture/*`, `api/<feature>.openapi.yaml`.
- **Output:**
  - **`_bmad-output/<feature>/dag.yaml`** (structure ONLY, see §5);
  - `epics-be/epic-N.md` + `epics-fe/epic-N.md` as **derived views generated** from `dag.yaml`+`prd.md` (never hand-written, see §4.6) — or removed if the user decides so (open decision §10);
  - red ATDD tests in the sub-repos (xUnit BE, jest/playwright FE).
- **Who:** `bmad-create-epics-and-stories` produces slices + `dag.yaml`; `bmad-testarch-atdd` + `bmad-testarch-test-design` scaffold the red tests in the respective repos (never cross-repo). Orchestrated by the user in main session.

### PHASE-3.5 — DAG entry gate *(survival-test checklist, incremental)*
- **Purpose:** the SINGLE door towards execution. Runs the survival-test checklist (Principle 7).
- **Incremental:** verifies ONLY the tasks candidate for promotion in this batch + their direct dependencies, **not** the whole backlog at every pass (so it scales beyond 35+ tasks).
- **Checks (all BLOCK if they fail):**
  - YAML contract absent or contract test not executable (even just RED) → BLOCKS;
  - `contract_ref` pointing to an `operationId` **nonexistent** in the YAML → BLOCKS;
  - `references` pointing to a **nonexistent anchor** in a sharded doc → BLOCKS;
  - task without concrete ACs / vague ACs → BLOCKS;
  - task exceeding the **leanness budget** (target 80-120 lines, see §6) or requiring more than N references → signal that the slice is too big → BLOCKS (split it);
  - **`dag.yaml` ↔ filesystem drift:** every declared `children[id]` has a file present, and every file in `tasks/**/` is declared as a node → orphans BLOCK (see §5.4 for WHO repairs).
- **Output:** **PASS** → promotion (`git mv` by the orchestrator) of the actionable tasks from `backlog/` to `todo/`. **BLOCKED** → report with the precise list of the misalignments and which phase to rework (1/2/2.5/3). Ephemeral verdict, not persisted.
- **Who:** `bmad-check-implementation-readiness` (EXTENDED with survival-test + contract-test executability + `operationId`/anchor resolution + leanness) + `bmad-review-edge-case-hunter` on the DAG and the tasks. The user confirms the gate.

### PHASE-4 — Per-side lean tasks *(generated from the contract's diff)*
- **Purpose:** materialize each leaf of the DAG into a LEAN task-file: boundary + Gherkin ACs + `depends_on` + `contract_ref` + `references`, SILENT on the "how" (Principle 6).
- **Generation from the diff:** tasks touching the boundary **are not written by hand**: they are GENERATED from the YAML's `git diff` (new/changed endpoint → 1 BE `produces` task + N FE `consumes` tasks with the same `contract_ref` by `operationId`).
- **Recurring contract AC (for every BE `produces` task):** the fan-out generates in the BE task an explicit AC *"a response-shape test on the real JSON body of this endpoint exists"* — this is the recurring per-endpoint work (not one-shot setup) that mitigates Swashbuckle fidelity. The verifier (owner of AC coverage) fails if it is missing.
- **Output:** `_bmad-output/<feature>/tasks/<side>/backlog/<slice>-<side>-<slug>.md` (target 80-120 lines). Format in §4.1.
- **Who:** `bmad-create-story` (RECONFIGURED lean) for each task; `bmad-testarch-test-design` maps AC→test. Driven in main session; the orchestrator computes the YAML's diff for the fan-out.

### PHASE-5 — Parallel BE‖FE execution
- **Purpose:** execute the actionable tasks in parallel: different sides = different repos = zero working-tree conflicts (Principle 8).
- **Input:** task-file (moved to `doing/` by the orchestrator), YAML via `contract_ref`, `be.md`/`fe.md`, prepared story branch.
- **Worker flow:** red-green-refactor in the correct repo; the side's contract test goes from RED to GREEN; self-review fix loop; commit per piece of functionality `bmad <SIDE>-<E>.<S>: ...` on the story branch.
- **Output:** diff in the correct sub-repo + commits on the story branch; the side's contract test GREEN; **strict return** (see §4.2). Task-file stays in `doing/`. **BOUNCED** (under-refined) → the orchestrator moves `doing/→backlog/` with a `## Worker note`, **does not re-dispatch**.
- **Who:** COMMAND **`dev-orchestrator-v2`** (<80 lines) computes the `ready_set` and dispatches SUBAGENT `mism-developer-lean`, one per side, `MAX_PARALLEL=3`, dedicated worktree `machinecare-<side>-worktrees/<task-id>` if two workers on the same side. The worker uses `mism-dev-story-lean` as the engine; `git-branching/gitflow.sh` for the branches. **Workers do NOT touch state nor `dag.yaml`.**

### PHASE-6 — Fresh-context verification *(structural gate + quality gate)*
- **Purpose:** double gate before the merge (Principle 9). SHARP boundary:
  - **(a) Structural verifier** (deterministic, read-only, virgin context): build + test + contract-test (BE+FE dry-run) + consistency with the MECHANICAL constraints of the ADRs (via `enforced_by` grep/lint, §4.5) + `contract_ref`-not-duplicated + ubiquitous-language grep + anti-shadow type check (§4.4.1). **It is the SOLE owner of AC coverage via tests.**
  - **(b) Adversarial code-review** (semantic): AC-by-AC, edges/bugs not covered by the tests, **and the discursive ADR consistency** (judgment, not determinism).
- **Source of the diff (authoritative = git, not the handoff):** the verifier computes `git -C <repo> diff $(git merge-base master <story-branch>)...<story-branch>`. It uses the worker's `FILE_LIST` ONLY as a **cross-check**: if the real diff contains files NOT in `FILE_LIST` → FAIL (the worker forgot/under-reported). Thus the ephemeral handoff becomes verifiable against the permanent truth.
- **Output:** Verifier `PASS|FAIL|SKIP` (max 2 re-dispatches with the findings, then escalation to the user). Code-review: HIGH/MEDIUM/LOW Review Findings with Decision/Patch/Defer/Dismiss triage, attached to the task in `done/` as an audit-trail after the merge. **The Defers become NEW DAG nodes** (see §5.4 for WHO writes the node), NOT entries in `deferred-work.md`.
- **Who:** SUBAGENT **`mism-verifier`** (read-only, parameterized `REPO_PATH`; handoff `PASS|FAIL|SKIP`); SKILL `bmad-code-review` (Blind/Edge/Acceptance Hunter) executed **in a virgin-context SUBAGENT** (not inline in main session — the user's main session accumulates PHASE-0..7 context, so it would not be "fresh"); `bmad-testarch-trace` for the AC↔test matrix.

### PHASE-7 — Release per slice *(cut of the DAG) with sequencing gate*
- **Purpose:** "Done" = this cut of the DAG is green and deployed (Principle 1).
- **Green slice:** all `children` (BE+FE) are in `done/` and merged onto `master`.
- **Sequencing gate at DEPLOY (not just merge):** an FE `consumes` task is not deployed before its BE `produces` is **deployed** and the contract test is green on `master` (closes the open risk of the FE calling a nonexistent endpoint). The source of "contract test green on master" is specified in §5.3.
- **Output:** squash-merge onto `master` in the sub-repos (`gitflow.sh`); INDEPENDENT BE/FE deploys respecting produces-before-consumes; green slice = DERIVED state shown on-demand by `dag-status`, never persisted. Optional: targeted `bmad-retrospective` post-slice (never post-sprint), by hand.
- **Who:** `dev-orchestrator-v2` (squash-merge + reports the green slice); per-repo CI (`bmad-testarch-ci`) with the contract test as the release gate; the user confirms the deploy respecting the sequencing.

---

## 3. Context budget (closes the "lean task → monolithic architecture" risk)

The lean task must NOT shift the context weight from the file to a monolithic architecture. Rules:

- The task's `references` point to **section anchors** (in docs sharded with `bmad-shard-doc`), not to "read `architecture-be-data-model.md`" (24KB) or `architecture-be-ocr-provider.md` (36KB).
- PHASE-3.5 verifies that every `reference` points to an existing anchor (same mechanism as `operationId`).
- **Budget per side:** a BE/FE task must not require more than **N=5 references** to derive the how. If more are needed → the slice is too big → split (BLOCK at the gate).
- The verifier, running on virgin context, loads **the same anchors pointed to by the task** (not the whole architecture): so "correct derivation from section X" is distinguishable from "invention".

---

## 4. Concrete file formats

### 4.1 Lean task-file
`tasks/<side>/backlog/<slice>-<side>-<slug>.md` — target **80-120 lines**.

```markdown
---
id: 2-2-be-get-maintenance-list      # derived from the filename, immutable
side: be                               # be | fe | sync | infra
repo: machinecare-be
slice: slice-2-recording-viewable
depends_on: [1-2-be-migration-tables] # list of ids (cross-slice too, see §5.2)
contract_ref:                          # LIST (a task can produce/consume multiple operations)
  - operationId: getMaintenanceByMachine
    role: produces                     # produces | consumes, per-operation
related_adrs: [0003-pagination-limit-1000]
references:                            # SECTION anchors, not whole files (budget §3)
  - architetture/architecture-be-data-model.md#maintenance-aggregate
  - be.md#repository-conventions
---

# Slice 2 / GET maintenance list per machine (BE)

## Acceptance Criteria (Gherkin)

Scenario: list filtered and sorted for an active machine
  Given a machine tool with 3 registered maintenance records
  When I call getMaintenanceByMachine with sort=data desc
  Then I receive 3 maintenance records sorted by descending date
  And the JSON body conforms to the contract's MaintenanceListItem schema

Scenario: a response-shape test on the real JSON body exists     # recurring contract AC (PHASE-4)
  Given the endpoint is implemented
  Then a test exists that asserts the real shape of the JSON body against the contract

## References
- architetture/api/<feature>.openapi.yaml#operationId=getMaintenanceByMachine
- architetture/architecture-be-data-model.md#maintenance-aggregate
- be.md#repository-conventions
```

**Forbidden in the task:** `status:`, `## Status`, `## File List`, `## Change Log`, `## Dev Agent Record`, `## Dev Notes`, `## Implementation Plan`. The state is the folder.

### 4.2 The worker's strict return (ephemeral, not persisted)
```
RESULT: READY-FOR-REVIEW | BLOCKED | BOUNCED
TASK_ID: 2-2-be-get-maintenance-list
BRANCH: machine-tools/2-2-be-get-list
SUMMARY: <1-2 sentences>
FILES_CHANGED: <n>
FILE_LIST: [path1, path2, ...]          # used only as a CROSS-CHECK by the verifier, not as a filter
TESTS_ADDED: [test1, ...]
TESTS_PASSING: true|false
```
The permanent journal is the sub-repo's `git log`. The verifier derives the diff from git (§PHASE-6), not from `FILE_LIST`.

### 4.3 `dag.yaml` (structure ONLY)
See §5.1.

### 4.4 Contract — `architetture/api/<feature>.openapi.yaml`
- The SINGLE source. Every operation has a **stable `operationId`** (the `contract_ref`s point to `operationId`, **never to a path JSON Pointer** — a path rename does not break the references).
- Every domain enum/object is a `components/schemas` **NAMED with the canonical name** (e.g. `InterventionType`), so `openapi-typescript` generates the type with the canonical name and an FE importing a different name fails at compile time.

```yaml
paths:
  /api/machine-tools/{machineId}/maintenance:
    get:
      operationId: getMaintenanceByMachine   # <- STABLE anchor of the contract_refs
      responses:
        '200':
          content:
            application/json:
              schema: { $ref: '#/components/schemas/MaintenanceListItem' }
components:
  schemas:
    InterventionType:                              # canonical domain name, NOT anonymous
      type: string
      enum: [ordinary, extraordinary]
```

#### 4.4.1 Honesty about drift: shape-equality ≠ domain-equality
The contract test captures the **shape**, not the ubiquitous language. Real example: the BE serializes the enum as `['ordinary','extraordinary']`, `openapi-typescript` generates an identical union on the FE — `tsc` does NOT fail even if the type NAMES diverge. Defenses (all necessary):
1. **Named schema** (above): the generated type has the canonical name → an FE importing `MaintenanceType` fails at compile time.
2. **Anti-shadow check in the verifier:** grep for `export type MaintenanceType` (or any hand-written domain type shadowing a generated type not imported from `api.generated.ts`) → FAIL.
3. Explicitly acknowledging that aligning the NAMES requires named `components/schemas`, not just path/operation.

#### 4.4.2 `api-backend-spec.md` — derived narrative (NOT hand-written)
To avoid the double-source disguised as "derived": `api-backend-spec.md` is **generated from the YAML** (redoc/widdershins → markdown) at every YAML change, or reduced to **pointers only** (`operationId` + 1 sentence of context per endpoint). Never hand-duplicated shapes/values. A CI hook regenerates-and-compares; if it diverges → FAIL.

### 4.5 ADR with mechanical constraint
```markdown
---
scope: be
status: accepted
supersedes: null
enforced_by: "grep -rn 'DefaultAzureCredential' src/ && ! grep -rn 'ConnectionString=' src/"
---
# 0004 — Blob access via Managed Identity, never connection string
```
Only ADRs with `enforced_by` are checked by the **verifier** (deterministic). Discursive ADRs (without `enforced_by`) are human input verified by the **code-review** (semantic). Honest about the boundary: the verifier does NOT judge prose.

### 4.6 `epics-N.md` — generated derived view (or removed)
If kept, they are **generated** from `dag.yaml`+`prd.md` (goal from the slice + FRs, sequencing from the edges), never hand-written, never a source. A hook regenerates them; if they drift → FAIL. If the user prefers, they are removed (open decision §10): `dag.yaml`+`prd.md` already cover goal and sequencing.

---

## 5. DAG model

### 5.1 Structure of `dag.yaml`
```yaml
slices:
  - id: slice-2-recording-viewable
    value: "Intervention recording viewable per machine"
    children: [2-1-be-post-create, 2-2-be-get-list, 1-3-fe-list-page]

# The task NODES are DERIVED from the files in tasks/** (filesystem authoritative, see §5.4).
# dag.yaml declares ONLY the EDGES:
edges:
  depends_on:
    - { from: 2-2-be-get-list, to: 1-2-be-migration-tables }   # cross-slice too
  contract:
    - { producer: 2-2-be-get-list, consumer: 1-3-fe-list-page, operationId: getMaintenanceByMachine }
```
**Iron constraint:** no `status` in `dag.yaml`.

### 5.2 Representable dependencies (closes the three holes of the model)
1. **`contract_ref`/`role` are LISTS** in the task: an FE task can `consumes` multiple operations (list+detail+stats) → N contract arcs from a single task.
2. **Cross-slice `depends_on`** is explicit and allowed. The slice→task hierarchy is about **RELEASE/state-derivation**, not dependency: dependencies live ONLY in the edges, never in the nesting. A cross-cutting technical dependency (e.g. design-system before every FE page; migration before every BE endpoint) is a normal cross-slice `depends_on`.
3. **`side` extended to `sync|infra`** for `machinecare-sync` (Marten) and `machinecare-infra`.

### 5.3 `ready_set` and the produces-before-consumes rule
A task is in the `ready_set` ⇔:
- (a) it is in `todo/`, and
- (b) every id in `depends_on` is a file in `done/`, and
- (c) for every contract arc where it is the `consumer`, the `producer` is in `done/` **and the producer's contract test is green on `master`**.

**Source of "contract test green on master" (specified, not manual):** before unblocking a consumer, `dev-orchestrator-v2` runs the producer's contract test locally on the sub-repo's `master` branch (`dotnet test --filter Contract`), or reads the CI job state via `gh run list --branch master`. This is an orchestrator check, not a ceremony for the user. (Open decision §10.)

### 5.4 WHO mutates `dag.yaml` and who is authoritative on the nodes *(closes the third-ledger risk)*
**Decision: the filesystem is authoritative on the NODES; `dag.yaml` declares ONLY the EDGES.**
- A task = a file in `tasks/**/`. The task-nodes are derived by globbing the files. There is no separate node-list to maintain → no file-vs-ledger divergence on the nodes.
- `dag.yaml` contains only `slices.children` (release view) + `edges`. When a **Defer** is born in PHASE-6:
  - the code-review (subagent) **proposes** the new task (file + `depends_on` edge towards the originating task) in its output;
  - the **orchestrator** (sole git-writer) writes the file in `backlog/` **and** adds the edge in `dag.yaml`, in a single transaction, and adds it to the slice's `children` if relevant.
- Thus a Defer never creates an orphan file: either the orchestrator completes the transaction, or it does not do it. PHASE-3.5 verifies file↔edge consistency anyway as a safety net.

### 5.5 How a machine traverses the DAG
`dev-orchestrator-v2`:
1. glob of the `done/` folders → `done` set;
2. reads `dag.yaml` (edges) + the frontmatter of the tasks in `todo/`;
3. computes the `ready_set` (§5.3);
4. topological dispatch in parallel, `MAX_PARALLEL=3`, one side per worker (BE and FE simultaneous = different repos = zero conflict); two tasks on the same side → dedicated worktrees `machinecare-<side>-worktrees/<task-id>`;
5. after every PASS+merge it recomputes `done` and repeats;
6. it stops when `todo/` and `doing/` are empty.

Cycle or `depends_on` towards a nonexistent id → empty `ready_set` with `todo/` not empty = **noisy deadlock** reported by `dag-status`.

### 5.6 On-demand aggregated view
`dag-status` command: reads file-positions + `dag.yaml`, prints green slices, ready tasks, deadlocks. Generated on the fly, **never persisted**.

---

## 6. Single-source state (state = the folder model)

Layout: `_bmad-output/<feature>/tasks/<side>/{backlog,todo,doing,done}/<slice>-<side>-<slug>.md`.

- **The physical position IS the state.** No `status:`, no `## Status`. Extinguishes **by construction** the double-state verified on 35/35 current BE tasks (e.g. `2-2`: frontmatter `done` / body `## Status` → `review`).
- **Transitions = `git mv`**, orchestrator/gate only:
  - PHASE-3.5 (gate): `backlog/ → todo/`;
  - orchestrator: `todo/ → doing/` when the worker starts; `doing/ → done/` after verifier PASS + code-review APPROVE + merge onto `master`;
  - BOUNCE: `doing/ → backlog/` + `## Worker note` (what is missing), not re-dispatched.
- **Slice state = DERIVED** (glob of the children in `done/`). Never written.
- **No ledger:** no `sprint-status.yaml` (already absent, kept that way). No reconciliation, no Most-advanced-wins, no veto.
- The sub-repos' `git log` is the truthful chronological journal. `deferred-work.md` (199 unprocessed lines) is **removed**: the Defers become DAG nodes (§5.4).

---

## 7. Verified contract — the single-source cycle

Four chained mechanisms:

1. **Single machine-readable source:** `api/<feature>.openapi.yaml`. Tasks point by `operationId` (stable under refactoring), they never duplicate the schema; the verifier checks that the diff POINTS and does not COPY. `api-backend-spec.md` is **generated** narrative (§4.4.2), never a second source.
2. **Producer (BE):** Swashbuckle already active (`Program.cs:26`). `ContractTests.cs` compares `swagger.json` with the YAML **+** a **real response-shape test per endpoint** (recurring AC of PHASE-4, mitigates a misconfigured swagger). RED in PHASE-3, GREEN in PHASE-5, runs with `dotnet test --filter Contract`.
3. **Consumer (FE):** `openapi-typescript` generates `src/types/api.generated.ts` (`prebuild` script); `api-service.ts` uses ONLY those types → a drift makes `tsc`/`npm run build` fail; `contract.test.ts` asserts by `operationId` that the endpoints in use exist. Plus the verifier's anti-shadow checks (§4.4.1).
4. **Diff→Task + Gate + CI:** the contract is changed ONLY on the YAML; the YAML's `git diff` GENERATES the tasks (PHASE-4). PHASE-3.5 BLOCKS if the YAML is missing, the contract test is not executable, or a `contract_ref` points to a nonexistent `operationId`. The verifier (PHASE-6) re-runs the BE+FE contract tests in dry-run before every merge. CI: two independent pipelines with the contract test as a blocking job.

**Versioning for non-additive breaking changes:** since deploys are independent, additive backwards-compatibility allows releasing one side without the other. A legitimate breaking change (field removal) requires a **versioning protocol** (new `operationId`/versioned path or version header) decided in an **ADR** BEFORE applying it.

### 7.1 Authorship of the contract — consumer-driven (read) / producer-driven (write)

The source remains **one** (the YAML); what changes is *who authors which part*. It is the user's explicit decision:

| Operation type | Who **authors** the schema | Executable verification |
|---|---|---|
| **Read** (GET / query / view) | the **FE**: it knows the views it needs (no speculative endpoints) | the **BE**'s CI must satisfy the read-schema → red if it does not satisfy it. This is true consumer-driven contract testing. |
| **Write** (POST/PUT/DELETE / command) | the **BE/domain**: it owns invariants and validation | the FE consumes the generated types; the FE's contract test fails if the shape diverges |
| **Arbitration + coherence** | the **architect** (`mism-architect`) | resolves feasibility/cost conflicts (the consumer knows what it *wants*, not what it *costs*) and keeps the contract cohesive |

**The pact broker already exists:** the shared location `_bmad-output/<feature>/architetture/api/` is the broker. The FE publishes the read-schemas there, the BE the write-schemas, **both CIs verify against it**. Zero copies in the tasks.

**Direction on the DAG:** for the reads the *authoring* goes consumer→producer (FE-design proposes the view → the BE realizes it → FE-build consumes the real endpoint), while the **runtime data** flows producer→consumer. The per-operation `produces`/`consumes` model (§5.1) holds both: for a read, the `contract` edge stays `producer: <BE-task>, consumer: <FE-task>` (whoever serves the data), but the *schema* of that operation was defined by the FE. The produces-before-consumes rule (§5.3) stays unchanged: the FE is not deployed before the BE actually serves that view.

---

## 8. Agents, skills, commands (Claude Code stack)

| Phase | Type | Claude Code artifact | Notes |
|---|---|---|---|
| 0 | skill | `bmad-product-brief`, `bmad-domain-research`/`bmad-brainstorming` | inline, the user |
| 1 | skill | `bmad-create-prd` → `bmad-validate-prd` → `bmad-review-adversarial-general` | loop with `bmad-edit-prd` |
| 2 | **subagent (NEW)** | `mism-architect` (engine: `bmad-create-architecture`) + `bmad-testarch-framework`/`-nfr` | produces YAML + ADRs; adversarial+edge-case review |
| 2.5 | skill+**subagent (NEW)** | `bmad-testarch-atdd`/`-framework`/`-ci`; `mism-developer-lean` for the contract tests | **deliverable: `mism-dev-story-lean` + `mism-developer-lean`** |
| 3 | skill | `bmad-create-epics-and-stories` (+`dag.yaml`), `bmad-testarch-test-design`/`-atdd` | red tests in the sub-repos |
| 3.5 | skill | `bmad-check-implementation-readiness` (EXTENDED) + `bmad-review-edge-case-hunter` | incremental gate |
| 4 | skill | `bmad-create-story` (RECONFIGURED lean) + `bmad-testarch-test-design` | fan-out from the YAML diff |
| 5 | **command (NEW)** | `dev-orchestrator-v2` (<80 lines) → subagent `mism-developer-lean` (engine `mism-dev-story-lean`) + `git-branching/gitflow.sh` | sole git-writer; MAX_PARALLEL=3 |
| 6 | **subagent (NEW)** | `mism-verifier` (read-only, `REPO_PATH`) + `bmad-code-review` **in a fresh subagent** + `bmad-testarch-trace` | sharp structural/semantic boundary |
| 7 | command+skill | `dev-orchestrator-v2` (squash-merge) + `bmad-testarch-ci`; optional `bmad-retrospective` post-slice | sequencing gate at deploy |

**SPECIALIZED WRITERS (the phases delegate; each writer owns format + survival test + is reused):**
- `mism-write-context-map` — bounded contexts + ubiquitous language + spikes (PHASE-0).
- `mism-write-infra-notes` — infra considerations (`infra-notes.md`) → `side: infra` tasks + `enforced_by` ADRs (PHASE-0/2).
- `mism-write-adr` — ADRs with `enforced_by` (PHASE-2+; used by `mism-create-contract`/architect/infra-notes).
- `mism-write-task` — lean task-file + `type: spike` nodes (PHASE-4 / Defer PHASE-6 / spikes from PHASE-0).

Principle: `mism-explore`, `mism-build-dag`, `mism-create-contract` are **thin orchestrators** that decide *what* to write; the **formats** are owned by the writers. New pipeline artifact: `infra-notes.md` (PHASE-0 draft → PHASE-2 consolidated), consumed by `mism-build-dag` (`side: infra` tasks) and by the `enforced_by` ADRs.

**UNCHANGED:** `git-branching` + `gitflow.sh` (branch per task `<feature>/<slice>-<side>-<slug>`, squash onto `master`, commits `bmad <SIDE>-<E>.<S>: ...`). Used only by the orchestrator.

**TO PRUNE from the critical path (they remain installed, out of the pipeline):** `bmad-sprint-planning`, `bmad-sprint-status`, `story-pipeline.md`, the current `dev-orchestrator.md` (288 lines), the `bmad-agent-*` persona wrappers, the `bmad-cis-*`, `bmad-prfaq`, `bmad-editorial-review-*`, `bmad-party-mode`/`tea`/`customize`/`help`/`bmb-setup`.

**REMOVED ARTIFACTS:** `sprint-status.yaml`, `deferred-work.md`, `## Status` body, `Dev Notes`/`Implementation Plan`/`File List`/`Change Log` in the tasks.

---

## 9. Summary of the four HIGH corrections from the critique (for traceability)

1. **Worker-does-not-write-state vs the `bmad-dev-story` engine that FORCES writing state** → create `mism-dev-story-lean` + `mism-developer-lean` as the **blocking deliverable of PHASE-2.5** + enforcement CI grep (§1.1, §PHASE-2.5).
2. **Fragile `contract_ref` (JSON Pointer on path) + false "endpoint-1..N" claim** → anchoring by **stable `operationId`**; claim removed; `operationId` normalization on all endpoints in PHASE-2 (§4.4).
3. **Verifier filtering the diff on the ephemeral `FILE_LIST`** → the verifier computes the diff from **git merge-base**, uses `FILE_LIST` only as a cross-check (§PHASE-6, §4.2).
4. **Responsibility hole: WHO writes the `dag.yaml` node when a Defer is born** → filesystem authoritative on the nodes; `dag.yaml` edges only; atomic file+edge transaction done by the orchestrator (§5.4).

---

## 10. Decisions still open (to be closed with the user)

1. **`epics-N.md`:** generate them automatically from `dag.yaml`+`prd.md` (derived view, never by hand) or remove them entirely? They already exist (`epics-be/epic-1..6`, `epics-fe/`). If they remain hand-written the rubric condemns them as zombies (no machine re-reads them).
2. **`api-backend-spec.md` (598 lines):** generate it from the YAML with redoc/widdershins at every change, or reduce it to `operationId`+1-sentence pointers only? Both close the drift; the former costs a tool in the pipeline, the latter loses the narrative readability.
3. **Source of "contract test green on master"** for the produces-before-consumes rule: does the orchestrator run `dotnet test --filter Contract` locally on master, or read `gh run list --branch master`? The former is self-sufficient but slower; the latter depends on CI and is faster but requires stably named CI jobs.
4. **Granularity of the `enforced_by` ADRs:** which architectural constraints deserve an executable grep/lint rule (e.g. Managed Identity) and which remain discursive (verified only by the code-review)? An initial list of `machinecare-be`'s mechanical constraints is needed.
5. **Context budget N=5 references per task:** is it the right number as the slice-split threshold, or should it be calibrated per side (BE vs FE) given the asymmetry of the architectures (ocr-provider 36KB on the BE side)?
6. **Contract versioning protocol** for non-additive breaking changes: versioned path (`/v2/...`) or version header? To be fixed in an ADR-template before it is needed.
7. **Canonical naming/location of the methodology:** `_bmad-output/methodology/mism-dag.md` (current choice) or `bmad-doc/`? To be decided before linking it from AGENTS.md.
8. **Worktree strategy** when two tasks of the same side and same slice run in parallel: shared `machinecare-<side>-worktrees/<task-id>` or per-slice? It impacts `gitflow.sh`'s paths and the merge.
9. **`side=sync` extension** (Marten/`machinecare-sync`): do the produces-before-consumes rule and the contract tests apply unchanged to event-sourced events/projections, or is a separate contract (event schema) with its own executable mechanism needed?
10. **`mism-dev-story-lean`:** a new skill written from scratch (current choice, avoids dragging in the ceremony of the 25KB engine) or a `lean` flag on `bmad-dev-story` (more DRY but touches the shared engine)?
