---
name: readiness-gate
description: 'mismAgent pre-flight before the build — an OPTIONAL early run of the worker-composer''s Phase 1 survival test, so you can catch an incomplete manifest before launching. It does NOT define its own checklist: the authority is the worker-composer Phase 1 (pinned boundary types, contract_test, projection, concrete tests_nl/ACs, executable gate, git present). Architecture-driven only (the file-driven dag/tasks gate is retired to attic). Use it to check a feature is ready, or just launch the worker-composer and let its Phase 1 do it.'
---

# MismAgent — Readiness pre-flight (model → build)

A **thin, optional pre-check**: it runs the **worker-composer's Phase 1** survival test *early*, so an
incomplete manifest is caught before you launch the build. **Ephemeral** verdict (not persisted).
There is **one** gate, and it lives in the worker-composer — this skill does not duplicate it.
Orientation: `methodology/mismagent.md`. You read the manifest (`building-blocks.yaml`, authoritative)
and the derived rich block files in `<output_dir>/<feature>/blocks/<ctx>/{todo,doing,done}/`.

## Principle: survival test
An artifact enters execution only if **something breaks loudly when it is wrong**. The gate makes that
test explicit *before* the workers waste effort.

## What it checks = the worker-composer's Phase 1 (the authority)
Run exactly that lens on `building-blocks.yaml` (do not invent extra rules):
- ∀ block: complete spec + **concrete acceptance** (`tests_nl`/ACs; a high-value block with no
  `tests_nl` → BLOCK, ask the user);
- ∀ boundary: **PINNED types** (Published Language, never the supplier's domain) + `contract_test` +
  `projection`; **cross-deploy** → its OpenAPI exists and every cited `operationId` resolves;
- the profile's **gate is executable**, and the side's repo is **under git** (the worker-composer
  init's it with confirmation if not);
- **leanness:** a block/slice that overflows its budget → too big → BLOCK (split with `build-manifest`).

## Useful verification commands (read-only)
```bash
# the rich block files must stay status-less — state is the FOLDER, never a field or a checkbox
grep -rlE '^status:' <output_dir>/<feature>/blocks/ && echo "VIOLATION: status field in a block file"
grep -rlE '^\s*- \[[ x]\]' <output_dir>/<feature>/blocks/ \
  && echo "VIOLATION: checkbox (progress-as-state) in a block file — the ## Task list is read-only criteria"
# cross-deploy only: operationIds declared in the YAML
grep -nE 'operationId:' <output_dir>/<feature>/architetture/api/<feature>.openapi.yaml 2>/dev/null
```

## Outcome
- **PASS** → say so and launch `/mismagent:worker-composer <feature>` (its Phase 1 re-runs this, the
  one authoritative gate). Verdict not persisted.
- **BLOCKED** → report the **precise** misalignments and **which step to rework** (architecture / the
  manifest / a missing `tests_nl`). Promote nothing.
- **EXPLICIT PENDING** → a `type: cleanup` node whose `ready_when` is not yet satisfied (waiting for
  consumers to migrate): list it separately — neither actionable nor an error.
