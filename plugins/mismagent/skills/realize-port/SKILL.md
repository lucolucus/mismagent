---
name: realize-port
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes a Port — consumer-owned interface, read-only, in PRIMITIVES (never the supplier's types) — the declaration of the inter-context boundary. Carries the spec of the consumer-driven contract test: reusable abstract class + factory, with a fake for the green-on-its-own. The projection (§13.B) decides whether the port stays in-process or is projected into OpenAPI. Loaded by the worker when block.type = port.
---

# realize-port — the declaration of the boundary, consumer-owned

You realize **ONE Port**: the interface with which a **consumer** context declares what it needs from
another. It is the **inter-context boundary** (Customer/Supplier relationship of the Context Map).
Rationale: `redesign/composer-spec.md` §2·§3·§9.

## The pattern
- **Consumer-owned:** the port belongs to the **consumer**, not to the supplier. It expresses the
  consumer's need, not the supplier's implementation.
- **Read-only, in primitives / Published Language:** the signature uses **primitive or shared-kernel**
  types, **never** the supplier's domain types (pinning Catalog's `ProductId` on a Sales port
  recreates the Sales→Catalog coupling). The identity at the boundary is the one **pinned in the
  manifest** (e.g. `Int`), not the `value class`.
- **Exposes named predicates, not raw fields:** the port offers `sellable`, not `active` — the
  boundary carries the decision already made by the root, not the state to be re-decided.

## The check (you carry it with you)
- **Consumer-driven contract test, reusable:** **abstract class + factory** of the subject-under-test,
  with a **fake** that makes it pass → the consumer is green on its own without the real supplier. The
  same test will later run on the **real Adapter** (D2): that is the point where the boundary is
  welded.
- **Translate the user's `tests_nl`** (§16) on the boundary into contract test cases (e.g. *"if I
  change the price, old sales keep the old price"* → a case that goes through the port).

## The projection (the worker-composer chooses it, §13.B)
- `seam-in-process` (single-side) → the port stays a code interface + in-process contract test.
- `seam-cross-deploy` (multi-side) → the port is projected into OpenAPI + per-side types + CDC (Pact).
You **do not distinguish**: you realize the interface + the contract test; skill B does the
projection.

## Return (to the worker)
`PUBLIC_API`: the port's signature + the schema of the reusable contract test (abstract class +
factory).
