---
name: realize-adapter
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes an Adapter — impl. of a Port, in two variants: READ (towards another context, delegates the predicate to the root, does not re-decide) and PERSISTENCE (repository, keeps the Aggregate agnostic of the technology). Carries the round-trip test and honors the §14 enforced_by gates (no DELETE/state writes from outside). Makes the port's consumer-driven contract test pass real-on-real (D2). Loaded by the worker when block.type = adapter.
---

# realize-adapter — the impl. of the boundary; does not re-decide, delegates

You realize **ONE Adapter**: the concrete implementation of a **Port**, or the **persistence** of an
Aggregate. Rationale: `redesign/composer-spec.md` §4·§9·§14.

## Two variants

### READ Adapter (towards another context)
- Implements a read port by **delegating the predicate to the root** of the supplier: it asks
  `prodotto.vendibile`, it does **not** re-read `attivo` and re-decide. (The port already exposes the
  named predicate.)
- Knows **only the public API** of the supplier (the signature), never its source nor its internal
  state.
- Makes the port's **consumer-driven contract test pass** (the one written by `realize-port`) — first
  on the fake, then real-on-real when the Composer re-runs it in **D2**.

### PERSISTENCE Adapter (repository)
- Keeps the Aggregate **agnostic of the technology**: the domain is pure, persistence lives here
  (hypothesis A, §9).
- **Round-trip test:** save → reload → the reconstructed Aggregate is equivalent (identity, state,
  invariants).
- It is the **only place** where the Aggregate's schema is touched (see gate below).

## The §14 gate (you honor it, the verifier checks it)
The persistence adapter is the **only one** authorized to write the Aggregate's tables:
- rule 1: no `INSERT/UPDATE/DELETE` on the Aggregate's tables **outside of here** (generalizes
  ADR-0002/0004: no `DELETE FROM prodotti`, no `UPDATE … prezzo_applicato`);
- you respect the `enforced_by` constraints declared in the block-spec's ADRs (soft-delete,
  write-once, …).

## The projection (the Composer chooses it, §13.B)
`seam-in-process` = adapter as a code object + in-process test. `seam-cross-deploy` = generated HTTP
client + CDC verify on the producer side. You realize the impl.; skill B fixes the medium.

## TDD + green on its own
`tdd` red-green-refactor. Self-review fix-loop on the **side's gate** until green, round-trip/contract
green, §14 gate respected.

## Return (to the worker)
`BOUNDARY_HONORED`: port contract test green? writes confined (§14 gate)? predicate delegated (not
re-decided)? yes/no.
