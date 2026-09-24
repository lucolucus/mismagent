---
name: mismagent-realize-read-model
description: "mismAgent worker block-type skill for `read-model`. Realizes a read-only query/projection (CQRS) whose output is the pinned view_shape, with a consumer-driven view test and folds that respect the wire's pinned guarantees. Loaded by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-read-model — the read projection (CQRS)

You realize **one read-model**: a query or projection serving a view to its consumer (typically the
UI).

## The pattern
- **Read-only, no domain rules.** It decides nothing: a predicate comes already computed from the
  root or the port, and reads of an aggregate's invariant fields go through that predicate. It
  never writes.
- **The output is the pinned `view_shape`** — field names and types are the Published Language
  towards the consumer. It may read several aggregates or tables.
- **A sync-fed fold follows the pinned guarantees:** read the boundary's `delivery:`; cross-stream
  order does not exist unless pinned. With more than one writer stream for the same key, implement
  what the manifest pinned — single-writer (fold only the owner's absolute stream) or a commutative
  fold (tombstones for a late entry, an orphan buffer for an effect before its cause). A fold that
  converges only when events arrive in order is a bug even when every shape matches.
- **Order only by fields pinned orderable.** "Sorted by X" is a contract on X's format; if the
  format is not pinned → `BOUNCED`, never sort and hope.

## The check you carry
- **A consumer-driven view test:** the `view_shape` without a test leaves the boundary unwelded.
- **Translate the user's `tests_nl`** into view test cases (shape and values).

## TDD, green on its own
Red-green-refactor on the side's gate until green and the view matches its shape.

## Return
`PUBLIC_API`: the realized `view_shape`.
