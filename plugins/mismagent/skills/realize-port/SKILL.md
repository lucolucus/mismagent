---
name: realize-port
description: mismAgent worker block-type skill for `port`. Realizes a consumer-owned port in Published Language types with its reusable consumer-driven contract test (abstract test + factory + fake, later the real adapter). Loaded by the worker.
user-invocable: false
---

# realize-port — the boundary's declaration, consumer-owned

You realize **one port**: the interface through which a consumer context declares what it needs from
a supplier (a Customer/Supplier relationship of the context map).

## The pattern
- **Consumer-owned:** it expresses the consumer's need, not the supplier's implementation.
- **Published Language only:** primitive or shared-kernel types as pinned in the manifest (a
  shared-kernel VO by default for correctness-critical types such as money and quantities), never
  the supplier's domain types (that would recreate the dependency the port cuts).
- **Named predicates, not raw fields:** the port offers `sellable`, not `active` — it carries the
  decision the root already made.

## The check you carry
- **A reusable consumer-driven contract test:** an abstract test + a factory for the subject under
  test, instantiated twice: on a **fake** of the port → the consumer is green without the real
  supplier (D1); on the **real adapter** (`realize-adapter`) → the weld (D2), re-run by the
  worker-composer on merge. Same test, fake and real: never a second, divergent copy.
- **Translate the user's `tests_nl`** on the boundary into contract test cases, the declared error
  cases included — never only the happy path.
- **One source for shared types:** a type the port shares already exists → import it, never redeclare.

## Return
`PUBLIC_API`: the port's signature and the reusable contract test (abstract test + factory).
