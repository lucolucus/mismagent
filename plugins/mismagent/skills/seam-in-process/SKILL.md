---
name: seam-in-process
description: mismAgent worker projection skill for `in-process` boundaries (same side). The port stays a code interface; its contract test runs in-process on a fake, then on the real adapter. Loaded with realize-port/realize-adapter.
user-invocable: false
---

# seam-in-process — the light boundary

Consumer and supplier live on the **same side**: the boundary crosses no deploy. Here a boundary is
"interface + test, nothing else" — what you would write anyway.

## What it adds to `realize-port` / `realize-adapter`
- **The port stays a code interface**; the consumer depends on it, the adapter implements it, both
  in the same side.
- **The contract test runs in-process**, the consumer-driven abstract test instantiated twice:
  1. on a **fake** of the port → the consumer is green on its own (D1);
  2. on the **real adapter** over the real supplier → the weld (D2), re-run by the worker-composer on
     merge.
- No generated types, no CDC publish/verify.

## The type at the boundary
Still **Published Language** as pinned in the manifest — a primitive or a shared-kernel VO (the
default for correctness-critical types such as money and quantities), never the supplier's domain
type. The strong type lives inside its context.

## When not this skill
`projection: cross-deploy` → `seam-cross-deploy`.
