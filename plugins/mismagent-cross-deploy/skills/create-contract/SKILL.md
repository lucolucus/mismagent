---
name: create-contract
description: 'Model movement of mismAgent — ONLY for boundaries with CROSS-DEPLOY projection (the OpenAPI is the cross-deploy projection of a Bounded Context boundary; in-process/single-side the port stays a code interface and this skill is NOT used). RECONCILES the API CONTRACT (executable OpenAPI YAML, single source) as a CONSEQUENCE of the manifest's blocks + boundaries: they declare the operations, here the shapes are filled in and the names are fixed from the ubiquitous language of explore. Stable operationIds, components/schemas with the canonical domain name, + the ADRs. Consumer-driven authorship on reads, producer-driven on writes; the architect arbitrates feasibility. Use after build-manifest when at least one boundary is cross-deploy.'
---

# MismAgent — Create Contract (model movement, cross-deploy projection only)

**When it is used:** only if at least one **boundary** has `projection: cross-deploy` (consumer and
supplier on different sides). The OpenAPI **is** the cross-deploy projection of a Bounded Context
boundary — if all boundaries are in-process (`contract: none`), the port stays a code interface
with its contract test and **this skill has no object**.

The contract is a **consequence of the manifest**, not its source: the `boundaries:` section of
`building-blocks.yaml` (the rows with `projection: cross-deploy`) and the blocks at each such
boundary declare *which* operations exist — a write per `application-service` command, a read per
view that crosses the boundary. Here you **reconcile them into ONE executable OpenAPI**, filling in
the shapes from the domain model and taking the **names** from the ubiquitous language of explore.
Orientation: `methodology/mismagent.md`. Write **only** in the parent
`<output_dir>/<feature>/architetture/` — never code in the sub-repos.

## Input
- **`building-blocks.yaml`** — the **`boundaries:`** rows with `projection: cross-deploy` (pinned
  types + `contract_test`) and the blocks at each such boundary: the supplier's
  `application-service` (`commands` → the writes), the consumer's `read-model`/`ui`
  (`view_shape`/`consumes_rm` → the reads);
- `context-map.md` — the **ubiquitous language** (= the canonical schema names) + the **tactical
  model**: commands → write endpoints, domain events → read-model, aggregates/invariants → write-schema + AC;
- `UI/` (visual source of the views for the reads), the per-side guides (from the profile), any contract to extend.

## Output
1. `architetture/api/<feature>.openapi.yaml` — **SINGLE source** of the contract.
2. `decisions/NNNN-<slug>.md` — the ADRs for the non-obvious choices.
3. (optional) `api-backend-spec.md` narrative **generated** from the YAML or reduced to pointers.

## Non-negotiable rules of the contract
- **STABLE and expressive `operationId`** for every operation. The manifest's boundaries (and the
  block files' `## Dependencies`, which inline the pinned signature) point to this, **never** to
  path JSON Pointers (a path rename must not break the refs).
- **`components/schemas` NAMED with the canonical domain name** (e.g. `InterventionType`, not
  an anonymous name): this way the **side's contract-test/types mechanism** (profile:
  `sides.<side>.contract`) generates the type with the canonical name, and a consumer side that
  imports a diverging name fails to compile. It defends against NAME drift, not only shape drift.
- **Never duplicate the schema** elsewhere. Blocks point to it, they do not copy it.

## Authorship — consumer-driven (read) / producer-driven (write)
The source is one; what changes is who authors what (the architect's authorship rule):

| Operation | Who authors the schema | Executable verification |
|---|---|---|
| **Read** (GET/query/view) | the **consumer side** (it knows the views it needs) | the **producer side's** gate must satisfy it → red if not |
| **Write** (POST/PUT/DELETE/command) | the **producer/domain side** (invariants, validation) | the consumer side consumes the types generated from the contract; its contract test breaks if the shape diverges |
| feasibility/coherence arbitration | **you (architect)** | counter-proposal + ADR when a view is infeasible/costly |

The shared location `architetture/api/` IS the **pact broker**: the consumer side publishes the
read-schemas, the producer side the write-ones, the gates of both sides verify against it.

## Errors and invariants on writes (the success shape is not enough)
A write has **two** pieces of contract beyond the success response:
- **Error response** `422 ValidationError` (with `fieldErrors`): it is **consumer-driven** — the
  consumer side consumes it to render the field errors. ALWAYS model it in the YAML (named
  `ValidationError` schema), not only the 200/201s.
- **Domain invariants** (cross-field rules, e.g. "subtype X valid only for category Y"):
  **take them from the "Tactical model" section of the `context-map.md`** (captured by
  `mismagent-tactical-modeler`), **do not reinvent them**. They are NOT expressible in OpenAPI (the shape does
  not capture them) → they remain in the **producer side's domain**. To make them executable truth,
  the supplier's `application-service` block must have an **AC on the invariant** (a `tests_nl` item
  that verifies the 422 when the invariant is violated). The `mismagent-verifier` checks that this
  AC has a test. The consumer side
  discovers them via 422 (which is why the 422 is contract, not extra).

## ADR — delegate to `write-adr`
Non-obvious decisions become ADRs: **invoke `write-adr`** (it owns format,
numbering, `supersedes`, `enforced_by` rule). Reminder: `enforced_by` (executable grep/lint,
checked by the `mismagent-verifier`) **only** for mechanical constraints; discursive ADRs are
verified by the code-review. Typical here: additive-vs-breaking choice, canonical naming
of a schema, access constraint (e.g. Managed Identity).

## Change on an EXISTING endpoint — additive vs breaking (decides the downstream fan-out)
Modifying an existing operation is normal; **always classify** the change (it decides whether the
consumer side can keep building in parallel):
- **Additive** (field/endpoint added, optional, backward-compatible): `operationId`
  unchanged. The consumer side can develop **in parallel** (it has the types generated
  from the contract); only the **deploy** is ordered (supplier-before-consumer).
- **Breaking** (removal/rename/type change): NOT in-place. It requires a **versioning
  protocol** (new `operationId`/versioned path or version header) decided in an **ADR
  before** applying it; there the consumer side depends-at-development on the new contract.

## Procedure (reconcile, do not invent upstream)
1. **Collect** from the manifest the cross-deploy boundaries and the operations their blocks imply
   (`application-service` `commands` → writes · `read-model`/`ui` views → reads): this is the
   **skeleton** of the operations that must exist, each under a declared `operationId`.
2. **Fill in the reads** (the views the consumer side's blocks need — `view_shape`, `consumes_rm`):
   named response schema, driven by the views in `UI/` (consumer-driven).
3. **Fill in the writes** (the commands the supplier side's `application-service` blocks expose):
   schema from the domain (invariants, validation — producer-driven), including the errors (see below).
4. **Names from the ubiquitous language:** every schema carries the canonical name from the
   `context-map` (one concept = one name). No synonyms.
5. For every feasibility/cost conflict: decide, write an ADR (via `write-adr`),
   possibly with a counter-proposal.
6. **Close the loop:** every operation the manifest's boundaries imply exists in the YAML and vice
   versa (no orphan endpoint, no boundary citing a non-existent `operationId` — the
   worker-composer's Phase 1 re-checks exactly this resolution).
7. The contract is executable truth only when the contract test harness exists on **both**
   sides; flag it if missing.

## Outcome
Summary: YAML path, list of `operationId`s with the owning side (writes on the supplier / reads
driven by the consumer), ADRs issued, authorship/feasibility decisions, points where the
requirements are ambiguous or an NFR is not verifiable.
