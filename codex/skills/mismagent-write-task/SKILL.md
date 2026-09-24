---
name: mismagent-write-task
description: "mismAgent model: writes the two node files that are not blocks \u2014 type: spike (an unknown, with its closure protocol) and type: cleanup (removing a deprecated published symbol, gated by ready_when) \u2014 under features/<feature>/tasks/<side>/<state>/."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# MismAgent — Write Task (spike / cleanup nodes)

Write a **node file** in `<output_dir>/features/<feature>/tasks/<side>/<state>/<slug>.md` (starting state
almost always `backlog/`). State **IS the folder** — no `status:` in the file. Orientation:
`methodology/mismagent.md`.

> **Not the implementation-task writer:** the units of work are the **blocks**
> (`blocks/<ctx>/<state>/<id>.md`).

## Template — `type: spike` node (unknown/research; from the context-map or a Defer)
```markdown
---
id: <slug>-spike
type: spike
side: <a side of the profile>
depends_on: []
central: false          # true = an unproven capability the product stands on: the
                        # worker-composer dispatches it at wave 0, beside the scaffold
---
# Spike / <question>

## Question to answer
<e.g. is this state persisted on the aggregate, or read at runtime from the other context?>

## Closure criterion
<what must exist to call it resolved: a decision in an ADR, a prototype, a measurement>

## Unblocks
- <block-id>
```
`## Unblocks` holds only `- <block-id>` lines (prose is ignored); empty until those blocks exist —
`build-manifest` fills it.

### Closing a spike (protocol)
An open spike **blocks** its consumers; close it like this, never by "deleting it":
1. **Where the decision lives:** if **mechanizable** → an **ADR** (with `enforced_by` checks if the
   constraint is mechanical); if **discursive** (e.g. UX) → folded into the **ACs / `tests_nl` of the consuming
   block**, with a dated note.
2. **The spike node goes to `done/`** (not deleted) with a `resolution:` field pointing to the
   consumer of the decision (`resolution: ADR-NNNN` or `resolution: AC of <block-id>`) — non-zombie trace.
3. **Who closes it:** in `build` the worker-composer moves it (sole git-writer of state) — a
   `central: true` spike it dispatched sits in `doing/` with its evidence in
   `features/<feature>/spikes/<id>.md` until the user decides; the decision is recorded by
   `write-adr` (or folded into the consuming blocks' ACs by `build-manifest`), then the composer
   moves the node to `done/`; in
   `explore`/`model` the conductor closes it mechanically once the user's answer is recorded: the
   context-map entry `[x]` with its `D-NNNN`/ADR reference, the node (if any) to `done/` with its
   `resolution:`. An answer never replaces the evidence a closure criterion demands.

## Template — `type: cleanup` node (removal of a deprecated published symbol, post-migration)
```markdown
---
id: <slug>-remove-v1
type: cleanup
side: <the side owning the symbol>
depends_on: []                          # NOT a task: readiness is a CONDITION, not an id
ready_when: "no-consumer-uses:<deprecated-symbol>"
---
# Cleanup / removal of <deprecated-symbol>

## What to remove
<the old operation/type + its tests, after ALL consumers have migrated>

## Readiness condition (ready_when)
No consumer references `<deprecated-symbol>` anymore — verifiable: grep the consumers' paths for it
(zero matches) and/or a contract test asserting "no calls to v1". While the condition
is false the node stays in `backlog/` as an **explicit pending** (the worker-composer's readiness
reports it), NEVER a deadlock.
```

## Outcome
Path of the node, id, kind (`spike`/`cleanup`), side, and which blocks/tasks it unblocks (spike)
or which deprecated symbol it retires under what `ready_when` (cleanup).
