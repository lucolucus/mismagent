---
name: seam-in-process
description: BOUNDARY-PROJECTION skill of the mismAgent worker (build, matrix §13.B). LIGHT variant of the boundary, chosen when consumer and supplier live on the same side (in-process projection, §8.3). The Port stays a CODE interface + the contract test runs in-process (fake on one side for the green-on-its-own). 'Interface + test, nothing else' — it is the proof that single-side is not ceremony. Loaded together with realize-port/realize-adapter when boundary.projection = in-process.
---

# seam-in-process — the light boundary (single-side)

You project an **in-process boundary**: consumer and supplier live on the **same side** → the boundary
does **not** cross a deploy. Rationale: `redesign/composer-spec.md` §8.3·§13.B. It is the proof that
single-side **is not ceremony**: here a boundary is *"interface + test, nothing else"* — what you
would write anyway.

## What it adds to `realize-port` / `realize-adapter`
- **The Port stays a code interface** (no projection onto HTTP/OpenAPI). The consumer depends on the
  **interface**, the Adapter implements it; both compiled in the same side.
- **The contract test runs in-process:** the **consumer-driven abstract class** (from `realize-port`)
  is instantiated twice —
  1. on a **fake** of the port → the consumer is green on its own (D1, without the real supplier);
  2. on the **real Adapter** on top of the real supplier → the welding of the boundary (D2), which the
     worker-composer re-runs on merge.
- **No generated types, no CDC publish/verify:** the boundary is code + test, all in the same process.

## The type at the boundary
It stays **Published Language** (primitive `Int` or shared-kernel), **not** the supplier's domain type
— even in-process: pinning the supplier's `value class` would recreate the coupling. The strong type
lives inside the context.

## When NOT this skill
If `boundary.projection = cross-deploy` (consumer and supplier on different sides) →
`seam-cross-deploy`.
