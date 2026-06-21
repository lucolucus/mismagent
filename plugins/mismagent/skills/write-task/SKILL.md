---
name: write-task
description: 'mismAgent''s specialized writer of the lean task-file. Produces tasks/<side>/<state>/<id>.md: boundary + Gherkin ACs + depends_on + contract_ref (by operationId) + references (anchors), MUTE on the how, state = the folder. Also handles type: spike (research/unknown node) + closure protocol and type: cleanup. SCOPE: the implementation-task template is the FILE-DRIVEN (legacy) flow; in the architecture-driven flow the BLOCKS in building-blocks.yaml + build-manifest''s derived tasks/ view replace it — there write-task only writes spike/cleanup nodes. Invoked by write-adr (cleanup), by the worker-composer (Defer), and to materialize the context-map''s spikes.'
---

# MismAgent — Write Task (writer, model / Defer / spike)

Write a **lean** task-file in `<output_dir>/<feature>/tasks/<side>/<state>/<id>.md` (the
starting state is almost always `backlog/`) — **but first check which flow you are in** (below):
in the architecture-driven flow this is only for spike/cleanup nodes. Orientation:
`methodology/mismagent.md`. Target **80-120 lines**.

## Which flow are you in? (do not recreate the #8 dual-paradigm muddle)
- **Architecture-driven (default):** the work-items are the **blocks** in `building-blocks.yaml`, and
  the human reads `build-manifest`'s **derived `tasks/T01..TNN.md` view** (flat, status-less). Do
  **NOT** write implementation tasks here — that view + the `blocks/<context>/{todo,doing,done}/`
  state replace them. write-task is used **only** for `type: spike` and `type: cleanup` nodes; keep
  them in their own `tasks/<side>/<state>/<id>.md` (stateful, `<id>` is a slug — never `T<NN>`, so they
  never collide with the derived `T01..TNN.md`/`README.md` files).
- **File-driven (legacy, `attic/`):** the full implementation-task template below is the unit of work.

## Invariants (also enforced by the `readiness-gate` and the CI guards)
- **No state in the file:** `status:` in the frontmatter and the sections `## Status`,
  `## File List`, `## Change Log`, `## Dev Agent Record`, `## Dev Notes`, `## Implementation Plan`
  are forbidden. State **IS the folder**.
- **No duplicated schema:** the task POINTS to the contract by `operationId`, it does not copy it.
- **Mute on the "how":** the worker derives the implementation from the sections in `references`.

## Template — implementation task
```markdown
---
id: <slice>-<side>-<slug>              # e.g. 6-7-be-statoocr-in-lista; derive the id from the filename
side: be | fe | sync | infra
repo: <repo of the chosen side — from the profile `sides.<side>.repo`>
slice: <slice-id>
depends_on: [<id>, ...]                # list, cross-slice allowed
contract_ref:                          # list; omit for tasks without a contract (e.g. infra)
  - { operationId: <opId>, role: produces|consumes }
related_adrs: [<NNNN-slug>, ...]
references:                            # SECTION anchors (budget ≤ ~5)
  - architetture/<doc>.md#<anchor>
---
# <Slice> / <title> (<side>)

## Acceptance Criteria (Gherkin)
Scenario: ...
  Given ... When ... Then ... And the body conforms to the contract schema
# for every BE produces task, add:
Scenario: a response-shape test on the real JSON body exists
  Then a test exists that asserts the real shape against the contract
# for a BE produces task of a WRITE, add invariants (← from the context-map, Tactical model section) + error contract:
Scenario: 422 when a domain invariant is violated
  Given an input that breaks a cross-field rule (e.g. invalid subtype for the category)
  When I invoke the command
  Then I receive 422 ValidationError with fieldErrors conforming to the contract schema

## References
- architetture/api/<feature>.openapi.yaml#operationId=<opId>
```

## Template — `type: spike` node (unknown/research; from the context-map or a Defer)
```markdown
---
id: <slug>-spike
type: spike
side: be | fe | sync | infra
repo: <repo of the side that will investigate>
slice: <slice-id | null>
depends_on: []
---
# Spike / <question>

## Question to answer
<e.g. is the OCR state already persisted on manutenzioni or must it be read at runtime from the OCR context?>

## Closure criterion
<what must exist to call it resolved: a decision in an ADR, a prototype, a measurement>

## Unblocks
<ids of the tasks that depend on this spike>
```

### Closing a spike (protocol)
An open spike **blocks** its consumers; it is closed like this, never by "deleting it":
1. **Where the decision lives:** if it is **mechanizable** → an **ADR** (with `enforced_by` if the
   constraint is mechanical); if it is **discursive** (e.g. UX) → folded into the **ACs / `tests_nl`
   of the consuming block or task**, with a dated note.
2. **The spike node goes to `done/`** (not deleted) with a `resolution:` field in the frontmatter
   pointing to the consumer of the decision (`resolution: ADR-NNNN` or
   `resolution: AC of <task/block-id>`) — non-zombie trace.
3. **Who closes it:** in `build` the orchestrator/worker-composer moves it (the only git-writer of
   state); in `model`/`explore` — where no orchestrator exists — it is closed by **whoever leads the
   movement in session**, noting it in the outcome. This is not a violation of "state = the folder":
   the monopolist rule holds inside build.

## Template — `type: cleanup` node (removal of a deprecated operationId, post-migration)
```markdown
---
id: <slug>-remove-v1
type: cleanup
side: be
repo: <repo that owns the deprecated endpoint>
slice: <slice-id | null>
depends_on: []                          # NOT a task: readiness is a CONDITION, not an id
ready_when: "no-consumer-uses:<deprecated-operationId>"
---
# Cleanup / removal of <deprecated-operationId>

## What to remove
<the old endpoint/operationId + its tests, after ALL consumers have migrated>

## Readiness condition (ready_when)
No consumer references `<deprecated-operationId>` anymore — verifiable: grep the FE/sync repos
for the old `operationId` (zero matches) and/or a contract test asserting "no calls to v1".
As long as the condition is false, the task stays in `backlog/` as an **explicit pending** (the
`readiness-gate` reports it, it does not leave it mute), NEVER as a deadlock.
```

## Leanness rule & dependencies
- If > ~5 `references` are needed or the file exceeds 120 lines → the **slice is too big**:
  do not write a giant task, signal `build-manifest` to split.
- Cross-slice `depends_on` is allowed. For an **additive** contract change on a read, the
  `consumes` task (consumer side) does **not** depend-for-development on the producer task (it has
  the types generated from the contract): the order matters only at **deploy** time (it is the
  worker-composer's CDC publish/verify, cross-deploy boundary). So do NOT add a producer→consumer
  `depends_on` for additive fields alone.

## Outcome
Path of the task, id, side/repo, contract_ref (or type:spike), and which tasks it unblocks.
