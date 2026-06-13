---
name: mism-readiness-gate
description: 'mismAgent gate between model and build. The SINGLE door towards execution: runs the survival-test checklist on the candidates (incremental). In the architecture-driven build the gate runs on the MANIFEST (= the Composer''s Phase 1: pinned boundary types, contract_test, projection); on the file-driven flow it verifies contract/operationId/anchors. Always: concrete ACs, leanness, state = the folder, structure↔filesystem consistency. Applies mismAgent''s survival test. Use before launching the Composer (or the legacy orchestrator) on a feature.'
---

# MismAgent — Readiness Gate (model → build)

The entry gate to the DAG. **Ephemeral** verdict (not persisted). Orientation:
`methodology/mismagent.md`. You work in the parent `<output_dir>/<feature>/`.

## Principle: survival test
An artifact enters execution only if **something breaks loudly when it is
wrong**. This gate makes that test explicit *before* the worker wastes work.

## Incremental
Verify **only** the tasks candidate for promotion in this batch + their direct
dependencies — **not** the entire backlog every time (so it scales beyond 35+ tasks).

## Checklist (every item BLOCKS if it fails)
Items **#1/#2 depend on the boundary projection** (from the profile) — do not demand an
OpenAPI where there is no cross-deploy boundary:
1. **Executable boundary:**
   - **cross-deploy** boundary → `architetture/api/<feature>.openapi.yaml` exists **and**
     the contract test harness is executable on both sides (RED is fine; non-executable is not);
   - **in-process / `contract: none`** boundary → the **port** exists as a declared interface
     (or `port` block in the manifest) with **pinned types** (Published Language: primitives or
     shared-kernel, never the supplier's domain), its mechanical constraint (`enforced_by`) is there,
     and the **consumer-driven contract test is specified** in the block/task that carries it.
2. **Boundary references resolvable:** every cited `operationId` exists in the YAML
   (cross-deploy); every boundary in the manifest has `projection` + `contract_test` (in-process).
   If there are no cross-deploy boundaries and no `operationId` is cited → n/a, do not block.
3. **`references` resolvable:** every pointed anchor exists in the corresponding sharded doc.
4. **Concrete ACs:** every task has verifiable Gherkin ACs; vague/missing AC → BLOCK.
5. **Leanness:** task within budget (target 80-120 lines, ≤ ~5 references). If it overflows → the
   slice is too big → BLOCK (to be split with `mism-build-manifest`).
6. **No state in the task:** no `status:` in the frontmatter, no `## Status`/
   `## File List`/`## Change Log`/`## Dev Agent Record` sections. State is the folder.
7. **`dag.yaml` ↔ filesystem consistency:** every `children[id]` has a file present; every file in
   `tasks/**/` is declared as a node. Orphans in either direction → BLOCK.
8. **`dag.yaml` without state:** no `status` field in `dag.yaml`.
9. **Tasks with `ready_when` (e.g. `type: cleanup`):** evaluate the condition (e.g.
   `no-consumer-uses:<operationId>` → grep the FE/sync repos for the old `operationId`). If it is
   still **false**, do NOT block the gate: report it as an **explicit pending** ("waiting for
   all consumers to migrate"), so it does not stay mute in `backlog/`. A malformed or
   non-evaluable `ready_when` → BLOCK.

## Useful verification commands (read-only)
```bash
# forbidden state in tasks
grep -rlE '^status:' <output_dir>/<feature>/tasks/ && echo "VIOLATION: status in frontmatter"
grep -rlE '^## (Status|File List|Change Log|Dev Agent Record)' <output_dir>/<feature>/tasks/
# forbidden state in the dag
grep -nE '^\s*status:' <output_dir>/<feature>/dag.yaml
# operationIds declared in the YAML
grep -nE 'operationId:' <output_dir>/<feature>/architetture/api/<feature>.openapi.yaml
```

## Outcome
- **PASS** → list the actionable tasks ready for promotion `backlog/ → todo/` (the `git mv`
  is done by the orchestrator, NOT this gate). Verdict not persisted.
- **BLOCKED** → report with the **precise** list of misalignments and **which phase
  to rework** (1 PRD / 2 contract / 2.5 harness / 3 DAG). Promote nothing.
- **EXPLICIT PENDING** → tasks with a `ready_when` not yet satisfied (e.g. cleanup waiting
  for consumers to migrate): list them separately, they are neither actionable nor an error.

After a PASS, launch `/mismagent:composer <feature>` (architecture-driven build; its
Phase 1 re-verifies the items on the manifest). The legacy file-driven flow lives in `attic/` and is
not invocable.
