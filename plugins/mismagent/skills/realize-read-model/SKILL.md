---
name: realize-read-model
description: mismAgent worker block-type skill for `read-model`. Realizes a read-only query/projection (CQRS) whose output is the pinned view_shape, with a consumer-driven view test and folds that respect the owner's declared guarantees. Loaded by the worker.
user-invocable: false
---

# realize-read-model — the read projection (CQRS)

You realize **one read-model**: a query or projection serving a view to its consumer (e.g. the UI).

## The pattern
- **Read-only, no domain rules.** It decides nothing: a predicate comes already computed from the
  root or the port, and reads of an aggregate's invariant fields go through that predicate. It
  never writes.
- **The output is the pinned `view_shape`** — field names and types are the Published Language
  towards the consumer. It may read several aggregates or tables.
- **A fold follows the guarantees in the owner's ADR Decision** (in your pack): order,
  duplicates/replay, who writes each key. Several writer streams per key → single-writer (fold only
  the owner's absolute stream) or a commutative fold (tombstones, an orphan buffer). Where the ADR
  admits reordering, a fold converging only on in-order events is a bug. Guarantee missing → `BOUNCED`.
- **Order only by fields pinned orderable.** "Sorted by X" is a contract on X's format; if the
  format is not pinned → `BOUNCED`, never sort and hope.

## The check you carry
- **A consumer-driven view test:** the `view_shape` without a test leaves the boundary unwelded.
- **Translate the user's `tests_nl`** into view test cases (shape, values; a fold: the admitted
  permutations and duplicates).

## TDD, green on its own
Red-green-refactor on the side's gate until green and the view matches its shape.

## Return
`PUBLIC_API`: the realized `view_shape`.
