---
name: seam-cross-deploy
description: BOUNDARY-PROJECTION skill of the mismAgent worker (build, matrix §13.B). HEAVY variant of the boundary, chosen when consumer and supplier live on different sides (cross-deploy projection, §8.3). The Port is projected into OpenAPI + per-side generated types + CDC publish/verify (Pact). It is the form mismAgent had always worked in — the old cross-side OpenAPI IS this projection of a Bounded Context boundary. Loaded together with realize-port/realize-adapter when boundary.projection = cross-deploy.
---

# seam-cross-deploy — the heavy boundary (multi-side)

You project a **cross-deploy boundary**: consumer and supplier live on **different sides**
(independent deploy-units) → the boundary crosses the network. Rationale:
`redesign/composer-spec.md` §8.3·§13.B. **Insight:** mismAgent's old cross-side OpenAPI **IS** this
projection of a Bounded Context boundary — here it is a *variant*, no longer the center of gravity.

## What it adds to `realize-port` / `realize-adapter`
- **The Port is projected into OpenAPI:** the consumer-owned signature (in primitives/Published
  Language) becomes a schema of the executable contract. Stable `operationId`s,
  `components/schemas` with the names of the ubiquitous language.
- **Per-side generated types:** the consumer (FE) generates the types from the contract → parallel
  development of the two sides *against the interface* (this is the "generated types → parallel
  development" — explicit here).
- **CDC publish/verify (Pact):** the consumer **publishes** the contract test (the pact); the producer
  **verifies** it real-on-real. The D2 welding is the pact verify on the producer side.
- **Authorship:** consumer-driven on reads, producer-driven on writes; the architect arbitrates
  feasibility.

## Producer-before-consumer (here, and only here)
The producer-before-consumer rule **survives as the CDC publish/verify** on the cross-side deploy —
no longer as a universal dogma of the orchestrator. At merge/deploy: additive-vs-breaking on the
contract, the producer must turn the pact green before the consumer depends on the new shape.

## When NOT this skill
If `boundary.projection = in-process` (consumer and supplier on the same side) → `seam-in-process`
(light).
