---
name: mismagent-realize-adapter
description: "mismAgent worker block-type skill (type adapter): the implementation of a Port \u2014 READ (delegates the predicate to the supplier root) or PERSISTENCE (the only writer of the aggregate's storage) \u2014 with its round-trip or contract test green."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-adapter — the boundary's implementation: it delegates, never re-decides

You realize **one Adapter**: the concrete implementation of a **Port**, or the **persistence** of
an Aggregate.

## The three guarantees (you honor them; the ADRs' checks and the reviewers verify them)
1. **Persistent writes only in the persistence adapter:** no insert/update/delete of an
   aggregate's stored state anywhere else.
2. **State changes go through the root:** the adapter stores what the root decided; it never
   mutates state the root did not produce, and never bypasses an invariant.
3. **Reads go through the root's named predicates:** a read adapter asks the supplier's predicate
   (e.g. `isSellable`); it never re-reads the raw fields and re-decides.

Plus the `enforced_by` checks of your block's ADRs (e.g. soft-delete, write-once) where they apply.

## Two variants

### READ adapter (towards another context)
- Implements a read port by **delegating to the supplier root's predicate** (the port exposes it).
- Knows **only the supplier's public API** (the signature), never its source or internal state.
- Makes the port's **consumer-driven contract test** (from `realize-port`) pass — on the fake
  first, then real-on-real when the composer runs it in the candidate.

### PERSISTENCE adapter (repository)
- Keeps the Aggregate **agnostic of the technology**: the domain stays pure, persistence lives here.
- **Round-trip test:** save → reload → the reconstructed Aggregate is equivalent (identity, state,
  invariants).
- The **only place** that touches the aggregate's storage schema (guarantee 1).

## The projection (the composer chooses it)
`seam-in-process` = the adapter as a code object + an in-process test. `seam-cross-deploy` =
generated client + consumer-driven verification on the producer side. You write the
implementation; the seam skill fixes the medium.

## TDD, green on its own
Red-green-refactor; fix-loop on the **side's gate** until green, round-trip/contract green, the
three guarantees held.

## Return (to the worker)
`BOUNDARY_HONORED`: contract/round-trip test green? writes confined? state through the root?
predicate delegated? yes/no.
