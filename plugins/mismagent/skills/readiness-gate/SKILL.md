---
name: readiness-gate
description: 'mismAgent pre-flight before the build — an OPTIONAL early run of the worker-composer''s Phase 1 survival test, so you can catch an incomplete manifest before launching. It does NOT define its own checklist: the authority is the worker-composer Phase 1 (pinned boundary types, contract_test, projection, concrete tests_nl/ACs, executable gate, git present). Architecture-driven only (the file-driven dag/tasks gate is retired to attic). Use it to check a feature is ready, or just launch the worker-composer and let its Phase 1 do it.'
---

# MismAgent — Readiness pre-flight (model → build)

A **thin, optional pre-check**: it runs the **worker-composer's Phase 1** survival test *early*, so an
incomplete manifest is caught before you launch the build. **Ephemeral** verdict (not persisted).
There is **one** gate, and it lives in the worker-composer — this skill does not duplicate it.
Orientation: `methodology/mismagent.md`. You read the manifest (`building-blocks.yaml`, authoritative)
and the derived rich block files in `<output_dir>/features/<feature>/blocks/<ctx>/{todo,doing,done}/`.

## Principle: survival test
An artifact enters execution only if **something breaks loudly when it is wrong**. The gate makes that
test explicit *before* the workers waste effort.

## What it checks = the worker-composer's Phase 1 (the authority)
Run exactly that lens on `building-blocks.yaml` (do not invent extra rules):
- ∀ block: complete spec + **concrete acceptance** (`tests_nl`/ACs; a high-value block with no
  `tests_nl` → BLOCK, ask the user);
- ∀ boundary: **PINNED types** (Published Language, never the supplier's domain) + `contract_test` +
  `projection`; **cross-deploy** → its **declared contract** exists in the form the boundary
  declares (`contract_form`: `openapi` → every cited `operationId` resolves · `event-schema` → the
  versioned schema files exist), **deferred** when the contract is an output of the wave-0 scaffold;
- the profile's **gate is executable and DISCRIMINATING** (Phase 1's red-green proof — a gate that
  cannot go red is not a gate), and the side's repo is **under git** (the worker-composer
  init's it with confirmation if not); a UI side with manual `ui_render_check` carries its
  **`run` binding** (pinned a priori — a gap here bounces to **the profile**, a targeted field edit).

## Useful verification commands (read-only)
```bash
# the rich block files must stay status-less — state is the FOLDER, never a field or a checkbox
grep -rlE '^status:' <output_dir>/features/<feature>/blocks/ && echo "VIOLATION: status field in a block file"
grep -rlE '^\s*- \[[ x]\]' <output_dir>/features/<feature>/blocks/ \
  && echo "VIOLATION: checkbox (progress-as-state) in a block file — the ## Tasks list is read-only criteria"
# cross-deploy only: operationIds declared in the YAML
grep -nE 'operationId:' <output_dir>/architetture/api/<feature>.openapi.yaml 2>/dev/null
```

## Outcome
- **PASS** → say so and launch `/mismagent:worker-composer <feature>` (its Phase 1 re-runs this, the
  one authoritative gate). Verdict not persisted.
- **BLOCKED** → report the **precise** misalignments and **which step to rework** (architecture / the
  manifest / a missing `tests_nl`). Promote nothing.
- **EXPLICIT PENDING** → a `type: cleanup` node whose `ready_when` is not yet satisfied (waiting for
  consumers to migrate), a **parked bounce** (`open-questions/<block-id>.md` awaiting the user), or
  an **open `type: spike` node** (its `Unblocks` blocks are not dispatched while it is open):
  list them separately — neither actionable nor an error. **Stale spikes** too: an `[ ]` entry in
  the context-map's "Open spikes" that an ADR already answers (close via `write-adr`'s
  `closes_spike` + `[x]`) or that was never materialized as a node — name them, never pass them in
  silence (friction-log-4 #13).
