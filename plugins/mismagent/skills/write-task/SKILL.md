---
name: write-task
description: 'mismAgent''s writer of the two NODE kinds the architecture-driven flow still needs as files: type: spike (a research/unknown node, with its closure protocol) and type: cleanup (removal of a deprecated cross-deploy operationId after consumers migrate, gated by ready_when). Writes <output_dir>/<feature>/tasks/<side>/<state>/<slug>.md, state = the folder. The old implementation-task is NOT here anymore: in the architecture-driven flow the work-items are the BLOCKS in building-blocks.yaml + build-manifest''s visible TASKS.md view; the file-driven implementation-task flow is retired to attic/. Invoked by write-adr (cleanup) and in explore/model to materialize the context-map''s spikes.'
---

# MismAgent — Write Task (spike / cleanup nodes)

Write a **node file** in `<output_dir>/<feature>/tasks/<side>/<state>/<slug>.md` (starting state
almost always `backlog/`). State **IS the folder** — no `status:` in the file. Orientation:
`methodology/mismagent.md`.

> **Not the implementation-task writer.** In the **architecture-driven** flow the units of work are
> the **blocks** in `building-blocks.yaml`, and the human reads them in `build-manifest`'s visible
> **`TASKS.md`** view — there is no per-feature implementation-task file. This skill writes only the
> two node kinds that are *not* blocks: **spike** and **cleanup**. The full implementation-task
> template of the superseded **file-driven** flow lives in **`attic/`**.
> *(De-confliction: these node files use **slug** ids under `tasks/<side>/<state>/`; the human view
> uses `TASKS/T01..TNN` at the project root — different place, different ids, no collision.)*

## Template — `type: spike` node (unknown/research; from the context-map or a Defer)
```markdown
---
id: <slug>-spike
type: spike
side: be | fe | sync | infra
repo: <repo of the side that will investigate>
depends_on: []
---
# Spike / <question>

## Question to answer
<e.g. is the OCR state already persisted on the aggregate, or read at runtime from the other context?>

## Closure criterion
<what must exist to call it resolved: a decision in an ADR, a prototype, a measurement>

## Unblocks
<ids of the blocks/tasks that depend on this spike>
```

### Closing a spike (protocol)
An open spike **blocks** its consumers; close it like this, never by "deleting it":
1. **Where the decision lives:** if **mechanizable** → an **ADR** (with `enforced_by` if the constraint
   is mechanical); if **discursive** (e.g. UX) → folded into the **ACs / `tests_nl` of the consuming
   block**, with a dated note.
2. **The spike node goes to `done/`** (not deleted) with a `resolution:` field pointing to the
   consumer of the decision (`resolution: ADR-NNNN` or `resolution: AC of <block-id>`) — non-zombie trace.
3. **Who closes it:** in `build` the worker-composer moves it (sole git-writer of state); in
   `model`/`explore` — where no orchestrator exists — whoever leads the movement in session closes it,
   noting it in the outcome. (Not a violation of "state = the folder": the monopolist rule holds inside build.)

## Template — `type: cleanup` node (removal of a deprecated cross-deploy operationId, post-migration)
```markdown
---
id: <slug>-remove-v1
type: cleanup
side: be
repo: <repo that owns the deprecated endpoint>
depends_on: []                          # NOT a task: readiness is a CONDITION, not an id
ready_when: "no-consumer-uses:<deprecated-operationId>"
---
# Cleanup / removal of <deprecated-operationId>

## What to remove
<the old endpoint/operationId + its tests, after ALL consumers have migrated>

## Readiness condition (ready_when)
No consumer references `<deprecated-operationId>` anymore — verifiable: grep the consumer repos for the
old `operationId` (zero matches) and/or a contract test asserting "no calls to v1". While the condition
is false the node stays in `backlog/` as an **explicit pending** (the worker-composer's Phase 1 reports
it, never leaves it mute), NEVER a deadlock.
```

## Outcome
Path of the node, id, kind (`spike`/`cleanup`), side/repo, and which blocks/tasks it unblocks (spike)
or which deprecated operationId it retires under what `ready_when` (cleanup).
