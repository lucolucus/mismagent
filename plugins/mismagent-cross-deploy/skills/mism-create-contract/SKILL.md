---
name: mism-create-contract
description: 'Model movement of mismAgent — ONLY for boundaries with CROSS-DEPLOY projection (the OpenAPI is the cross-deploy projection of a Bounded Context boundary; in-process/single-side the port stays a code interface and this skill is NOT used). RECONCILES the API CONTRACT (executable OpenAPI YAML, single source) as a CONSEQUENCE of the blocks/tasks: they declare the operationIds, here the shapes are filled in and the names are fixed from the ubiquitous language of explore. Stable operationIds, components/schemas with the canonical domain name, + the ADRs. Consumer-driven authorship on reads, producer-driven on writes; the architect arbitrates feasibility. Use after mism-build-manifest when at least one boundary is cross-deploy.'
---

# MismAgent — Create Contract (model movement, cross-deploy projection only)

**When it is used:** only if at least one **boundary** has `projection: cross-deploy` (consumer and
supplier on different sides). The OpenAPI **is** the cross-deploy projection of a Bounded Context
boundary — if all boundaries are in-process (`contract: none`), the port stays a code interface
with its contract test and **this skill has no object**.

The contract is a **consequence of the blocks/tasks**, not their source: they declare
*which* operations exist — one `operationId` for every supplier-`produces` /
consumer-`consumes` pairing. Here you **reconcile them into ONE executable OpenAPI**, filling in
the shapes from the domain model and taking the **names** from the ubiquitous language of explore.
Orientation: `methodology/mismagent.md`. Write **only** in the parent
`<output_dir>/<feature>/architetture/` — never code in the sub-repos.

## Input
- the **tasks** in `tasks/**/` with their `contract_ref` (the declared `operationId`s + `role`);
- `context-map.md` — the **ubiquitous language** (= the canonical schema names) + the **tactical
  model**: commands → write endpoints, domain events → read-model, aggregates/invariants → write-schema + AC;
- `UI/` (visual source of the views for the reads), the per-side guides (from the profile), any contract to extend.

## Output
1. `architetture/api/<feature>.openapi.yaml` — **SINGLE source** of the contract.
2. `decisions/NNNN-<slug>.md` — the ADRs for the non-obvious choices.
3. (optional) `api-backend-spec.md` narrative **generated** from the YAML or reduced to pointers.

## Non-negotiable rules of the contract
- **STABLE and expressive `operationId`** for every operation. The tasks' `contract_ref`
  point to this, **never** to path JSON Pointers (a path rename must not break the refs).
- **`components/schemas` NAMED with the canonical domain name** (e.g. `InterventionType`, not
  an anonymous name): this way the **side's contract-test/types mechanism** (profile:
  `sides.<side>.contract`) generates the type with the canonical name, and a consumer side that
  imports a diverging name fails to compile. It defends against NAME drift, not only shape drift.
- **Never duplicate the schema** elsewhere. Tasks point to it, they do not copy it.

## Authorship — consumer-driven (read) / producer-driven (write)
The source is one; what changes is who authors what (§7.1 of the methodology):

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
  `mism-analyst`), **do not reinvent them**. They are NOT expressible in OpenAPI (the shape does
  not capture them) → they remain in the **producer side's domain**. To make them executable truth,
  the producer task must have an **AC on the invariant** (a test that verifies the 422 when the
  invariant is violated). The `mism-verifier` checks that this AC has a test. The consumer side
  discovers them via 422 (which is why the 422 is contract, not extra).

## ADR — delegate to `mism-write-adr`
Non-obvious decisions become ADRs: **invoke `mism-write-adr`** (it owns format,
numbering, `supersedes`, `enforced_by` rule). Reminder: `enforced_by` (executable grep/lint,
checked by the `mism-verifier`) **only** for mechanical constraints; discursive ADRs are
verified by the code-review. Typical here: additive-vs-breaking choice, canonical naming
of a schema, access constraint (e.g. Managed Identity).

## Change on an EXISTING endpoint — additive vs breaking (decides the downstream fan-out)
Modifying an existing operation is normal; **always classify** the change (used by
`mism-build-dag` for the dependencies):
- **Additive** (field/endpoint added, optional, backward-compatible): `operationId`
  unchanged. The consumer side (`consumes`) can develop **in parallel** (it has the types generated
  from the contract); only the **deploy** is ordered (produces-before-consumes). No `depends_on`
  producer→consumer.
- **Breaking** (removal/rename/type change): NOT in-place. It requires a **versioning
  protocol** (new `operationId`/versioned path or version header) decided in an **ADR
  before** applying it; there the consumer side depends-at-development on the new contract.

## Procedure (reconcile, do not invent upstream)
1. **Collect** from the tasks all the declared `operationId`s (with `role` produces/consumes): this is
   the **skeleton** of the operations that must exist.
2. **Fill in the reads** (the views that the consumer side's `consumes` tasks need): named response
   schema, driven by the views in `UI/` (consumer-driven).
3. **Fill in the writes** (the commands that the producer side's `produces` tasks declare): schema
   from the domain (invariants, validation — producer-driven), including the errors (see below).
4. **Names from the ubiquitous language:** every schema carries the canonical name from the
   `context-map` (one concept = one name). No synonyms.
5. For every feasibility/cost conflict: decide, write an ADR (via `mism-write-adr`),
   possibly with a counter-proposal.
6. **Close the loop:** every `operationId` declared by the tasks exists in the YAML and vice versa
   (no orphan endpoint, no task pointing to a non-existent `operationId`).
7. The contract is executable truth only when the contract test harness exists on **both**
   sides; flag it if missing.

## Outcome
Summary: YAML path, list of `operationId`s with expected `role` (produces on the producer side /
consumes on the consumer side), ADRs issued, authorship/feasibility decisions, points where the
PRD is ambiguous or an NFR
is not verifiable.
