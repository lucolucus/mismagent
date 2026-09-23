---
name: mismagent-write-task
description: "mismAgent''s writer of the two NODE kinds the architecture-driven flow still needs as files: type: spike (a research/unknown node, with its closure protocol) and type: cleanup (removal of a deprecated cross-deploy operationId after consumers migrate, gated by ready_when). Writes <output_dir>/features/<feature>/tasks/<side>/<state>/<slug>.md, state = the folder. The old implementation-task is NOT here anymore: in the architecture-driven flow the work-items are the BLOCKS (rich files in blocks/, viewed via $mismagent-board); the file-driven implementation-task flow is retired to attic/. Invoked by write-adr (cleanup) and by the tactical-modeler in model to materialize the context-map''s spikes."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# MismAgent — Write Task (spike / cleanup nodes)

Write a **node file** in `<output_dir>/features/<feature>/tasks/<side>/<state>/<slug>.md` (starting state
almost always `backlog/`). State **IS the folder** — no `status:` in the file. Orientation:
`methodology/mismagent.md`.

> **Not the implementation-task writer.** In the **architecture-driven** flow the units of work are
> the **blocks** (rich `<id>.md` files in `blocks/<ctx>/{todo,doing,done}/`, viewed live via
> `$mismagent-board`) — there is no per-feature implementation-task file. This skill writes only the
> two node kinds that are *not* blocks: **spike** and **cleanup**. The full implementation-task
> template of the superseded **file-driven** flow lives in **`attic/`**.
> *(De-confliction: spike/cleanup nodes live under **`tasks/`**`<side>/<state>/`; the blocks live under
> **`blocks/`**`<ctx>/<state>/` — different trees, no collision.)*

## Template — `type: spike` node (unknown/research; from the context-map or a Defer)
```markdown
---
id: <slug>-spike
type: spike
side: be | fe | sync | infra
depends_on: []
central: false          # true = an unproven capability the product stands on (build-manifest
                        # rule 22): the worker-composer dispatches it at wave 0, beside the scaffold
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
3. **Who closes it:** in `build` the worker-composer moves it (sole git-writer of state) — a
   `central: true` spike it dispatched sits in `doing/` with its evidence in
   `features/<feature>/spikes/<id>.md` until the user decides; the decision is recorded by
   `write-adr` (or folded into the consuming blocks' ACs by `build-manifest`), then the composer
   moves the node to `done/`; in
   `model`/`explore` — where no orchestrator exists — whoever leads the movement in session closes it,
   noting it in the outcome. (Not a violation of "state = the folder": the monopolist rule holds inside build.)

## Template — `type: cleanup` node (removal of a deprecated cross-deploy operationId, post-migration)
```markdown
---
id: <slug>-remove-v1
type: cleanup
side: be
depends_on: []                          # NOT a task: readiness is a CONDITION, not an id
ready_when: "no-consumer-uses:<deprecated-operationId>"
---
# Cleanup / removal of <deprecated-operationId>

## What to remove
<the old endpoint/operationId + its tests, after ALL consumers have migrated>

## Readiness condition (ready_when)
No consumer references `<deprecated-operationId>` anymore — verifiable: grep the consumers' paths for the
old `operationId` (zero matches) and/or a contract test asserting "no calls to v1". While the condition
is false the node stays in `backlog/` as an **explicit pending** (the worker-composer's Phase 1 reports
it, never leaves it mute), NEVER a deadlock.
```

## Outcome
Path of the node, id, kind (`spike`/`cleanup`), side, and which blocks/tasks it unblocks (spike)
or which deprecated operationId it retires under what `ready_when` (cleanup).
