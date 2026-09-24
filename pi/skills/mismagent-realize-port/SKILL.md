---
name: mismagent-realize-port
description: "mismAgent worker block-type skill for `port`. Realizes a consumer-owned port in Published Language types with its reusable consumer-driven contract test (abstract test + factory + fake). Loaded by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-port — the boundary's declaration, consumer-owned

You realize **one port**: the interface through which a consumer context declares what it needs from
a supplier (a Customer/Supplier relationship of the context map).

## The pattern
- **Consumer-owned:** it expresses the consumer's need, not the supplier's implementation.
- **Published Language only:** primitive or shared-kernel types as pinned in the manifest, never the
  supplier's domain types (that would recreate the dependency the port cuts).
- **Named predicates, not raw fields:** the port offers `sellable`, not `active` — it carries the
  decision the root already made.

## The check you carry
- **A reusable consumer-driven contract test:** an abstract test + a factory for the subject under
  test, with a **fake** that passes it, so the consumer is green without the real supplier. The same
  test later runs on the real adapter (D2): that is where the boundary is welded.
- **Translate the user's `tests_nl`** on the boundary into contract test cases.

## The projection (chosen by the manifest's `projection`)
- `seam-in-process` — the port stays a code interface with an in-process contract test.
- `seam-cross-deploy`, `openapi` — the port is projected into the contract + generated types + CDC.
- `seam-cross-deploy`, `event-schema` — the schema is the contract and there is no remote supplier
  to fake: the abstract test + factory survive, the "fake" becomes a mutated descriptor
  (descriptor-reflection CDC).

You realize the interface and the contract test; the seam skill adds the projection.

## Return
`PUBLIC_API`: the port's signature and the reusable contract test (abstract test + factory).
