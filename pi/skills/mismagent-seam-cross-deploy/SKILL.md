---
name: mismagent-seam-cross-deploy
description: "mismAgent worker projection skill for `cross-deploy` boundaries. Projects the port into its declared contract (OpenAPI or a versioned event-schema) with per-side generated types and CDC publish/verify. Loaded with realize-port/realize-adapter."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> Cross-deploy module: install only when a boundary crosses a deploy unit
> (`install.sh --with-cross-deploy`).

# seam-cross-deploy — the boundary across deploy units

Consumer and supplier live on **different sides**: the boundary crosses the network, in the
`contract_form` the manifest declares.

## `openapi` — request/response
- **The port is projected into the contract:** its Published-Language signature becomes the
  executable OpenAPI (stable `operationId`s, `components/schemas` with canonical names — reconciled
  by `create-contract`).
- **Per-side generated types:** each side generates its types from the contract, so both develop in
  parallel against the interface.
- **CDC publish/verify:** the consumer publishes its contract test; the producer verifies it
  real-on-real. The D2 weld is the producer-side verify.
- **Authorship:** reads consumer-driven, writes producer-driven; the architect arbitrates.
- **Producer before consumer** survives only here, at deploy: classify each contract change as
  additive or breaking; the producer turns the verify green before the consumer depends on the new
  shape.

## `event-schema` — replication/sync wires
- The contract is the **versioned schema** at the declared `schema_paths`: additive evolution only,
  versioning protocol fixed in an ADR before the first breaking touch; types generated from the
  schema per side; canonical names on events and messages; CDC runs on the events.
- **The CDC is descriptor reflection:** the schema is the single source of the types and there is
  no remote supplier to fake. The contract test loads the compiled schema descriptors; the "fake" is
  a descriptor **mutated in memory** (a field or event removed or renamed) that must turn the test
  red — red on removal and on rename is the mechanical proof that evolution stays additive.
- **The wire pins its delivery guarantee** (`delivery:` on the boundary, owed by the sync adapter):
  consumer folds are designed against it — single-writer-per-key or a declared commutative fold —
  and the D2 weld exercises it. A fold that converges only under a stronger guarantee than the pinned
  one is a defect even when every shape matches.

## When not this skill
`projection: in-process` → `seam-in-process`.
