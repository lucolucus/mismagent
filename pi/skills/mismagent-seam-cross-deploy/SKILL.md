---
name: mismagent-seam-cross-deploy
description: "BOUNDARY-PROJECTION skill of the mismAgent worker (build, matrix \u00a713.B). HEAVY variant of the boundary, chosen when consumer and supplier live on different sides (cross-deploy projection, \u00a78.3). The Port is projected into OpenAPI + per-side generated types + CDC publish/verify (Pact). It is the form mismAgent had always worked in \u2014 the old cross-side OpenAPI IS this projection of a Bounded Context boundary. Loaded together with realize-port/realize-adapter when boundary.projection = cross-deploy."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> Cross-deploy module: install only when a boundary crosses a deploy unit
> (`install.sh --with-cross-deploy`).

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

## The `event-schema` form (replication/sync wires)
When the boundary declares **`contract_form: event-schema`** (event-replication, local-first sync,
warm-standby coordination — decided by an ADR), the projection is **not** OpenAPI: the contract is
the **versioned event-schema** at the declared `schema_paths` (e.g. proto + event catalogue),
**additive evolution** only, versioning protocol fixed in the ADR before the first breaking touch.
Same discipline, different artifact: per-side **generated types from the schema**, canonical names
from the ubiquitous language on events/messages, and the **CDC runs on the events** (the consumer
publishes what it expects to replicate/receive; the producer verifies real-on-real at D2). OpenAPI
is the *request/response* form of cross-deploy, not its definition (friction-log-4 #5/#16).

**The CDC of a schema contract is DESCRIPTOR-REFLECTION** (friction-log-4 #36): here the schema
**is** the contract (single source of the types) and there is no remote supplier to fake — adapt
`realize-port`'s abstract+factory+fake pattern accordingly: the contract test loads the compiled
schema **descriptors** (e.g. proto `FileDescriptorProto`) and the "fake" is a descriptor **mutated
in memory** (a field/event removed or renamed) that must turn the test **RED** —
red-on-removal/red-on-rename is the mechanical proof that additive evolution holds. Proven
realizable in a real run; reuse the pattern, don't reinvent it per project.

**The wire also PINS its DELIVERY guarantee** (friction-log-4 #50): the contract is not just the
event shapes — it includes the **`delivery:`** the manifest pins on the boundary (e.g. per-node
in-order + dedup(nodeId, seq) **before** the fold, owed by the sync adapter/engine). Consumers'
folds are designed against it — single-writer-per-key, or a declaredly commutative fold
(build-manifest rule 17) — and the D2 weld exercises it: a fold that converges only under a
stronger guarantee than the pinned one is a defect even when every shape matches.

## When NOT this skill
If `boundary.projection = in-process` (consumer and supplier on the same side) → `seam-in-process`
(light).
