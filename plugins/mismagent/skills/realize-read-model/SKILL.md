---
name: realize-read-model
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes a read-model — query/projection (CQRS) whose output respects the view_shape pinned in the manifest. Read-only, no domain rules (those live on the Aggregate). Carries the view test: consumer-driven contract test where the consumer is the UI. Loaded by the worker when block.type = read-model.
---

# realize-read-model — the read projection (CQRS)

You realize **ONE read-model**: a query/projection that serves a view to a consumer (typically the
UI). It is the **read side** of CQRS. Rationale: `redesign/composer-spec.md` §1·§8.

## The pattern
- **Read-only, zero domain rules:** a read-model **decides** nothing — the rules live on the
  Aggregate. If you need a predicate, you take it already computed (the root/port exposes it), you do
  not recompute it.
- **The output respects the `view_shape`** pinned in the manifest: the view's fields, types and names
  are the **Published Language** towards the consumer, not an internal detail.
- It may aggregate from multiple aggregates/tables when reading, but it remains a projection: no
  writes.

## The check (you carry it with you)
- **Contract test of the view, consumer-driven:** the **consumer is the UI** → the view is pinned
  *and* verified (the `view_shape` alone, without a test, leaves the boundary unwelded — gap closed in
  Phase-1 readiness).
- **Translate the user's `tests_nl`** (§16) into view test cases (e.g. *"the history shows the shift's
  takings"* → a case on the shape and the values).

## TDD + green on its own
`tdd` red-green-refactor. Self-review fix-loop on the **side's gate** until green and the view
respects the shape.

## Return (to the worker)
`PUBLIC_API`: the realized `view_shape` (the signature the UI consumes).
