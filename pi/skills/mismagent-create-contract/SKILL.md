---
name: mismagent-create-contract
description: "mismAgent model movement, cross-deploy only. Reconciles the OpenAPI of each openapi boundary from the manifest \u2014 stable operationIds, canonical schema names, declared errors \u2014 extending an existing contract. Use after build-manifest."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> Cross-deploy module: install only when a boundary crosses a deploy unit
> (`install.sh --with-cross-deploy`).

# mismAgent — Create Contract (cross-deploy, `openapi` form)

**Scope:** only boundaries with `projection: cross-deploy` **and** `contract_form: openapi`
(request/response between sides). In-process boundaries stay code interfaces; an `event-schema` wire
follows the same disciplines (single source at its `schema_paths`, canonical names, additive
evolution with a versioning ADR, the pinned `delivery:` guarantee) on its schema files, not here —
see `seam-cross-deploy`. Orientation: `methodology/mismagent.md`.

Write only in `<output_dir>/architetture/` and, via `write-adr`, `<output_dir>/decisions/`. Never code
in the sides' paths.

## The contract belongs to the BOUNDARY, not to the feature
Before generating anything, scan **all** `<output_dir>/architetture/api/*.openapi.yaml` for a
contract that already covers this boundary (same consumer/supplier pair). A new feature has no file
of its own by construction; if a contract exists **under any name**, extend that file under the
additive-vs-breaking discipline and report the **delta** (operations added / changed / unchanged).
Only a boundary with no contract gets a new `architetture/api/<feature>.openapi.yaml`, named after
the feature that introduced it — for the project's life. Report its path so the manifest's
`contract_path` points at it.

## Input
- `building-blocks.yaml`: the cross-deploy `boundaries:` rows (pinned types, `operation_ids`,
  `contract_test`) and the blocks at each — the supplier's `application-service` `commands` (writes),
  the consumer's `read-model`/`ui` views (reads);
- `<output_dir>/context-map.md` (canonical names) and `features/<feature>/tactical-model.md`
  (commands, events, invariants);
- `UI/` for the views, the per-side guides, the contract to extend.

## Rules of the contract
- Every operation has a **stable, expressive `operationId`**; manifests and block files reference
  it, never a path pointer.
- Every domain enum/object is a `components/schemas` entry **named with the canonical domain
  name**, so each side's type generation (profile `sides.<side>.contract`) fails to compile on a
  divergent name.
- **One source:** never duplicate a schema elsewhere; a narrative spec is generated from the YAML or
  reduced to pointers.
- **Authorship:** reads are shaped by the **consumer** (the producer's gate must satisfy them);
  writes by the **producer/domain** (the consumer builds on the generated types). An infeasible or
  costly view → counter-proposal + ADR. The shared `architetture/api/` is where both sides publish
  and verify.

## Errors and invariants on writes
- Model every **error response the contract declares** for a write (for example a validation error
  with per-field detail) as a named schema, not only the success responses — the consumer renders
  them.
- **Domain invariants** come from the tactical model, never reinvented. OpenAPI cannot express them:
  they stay in the producer's domain, and the supplier's `application-service` block carries an AC
  (a `tests_nl` item) proving the declared error when the invariant is violated. The verifier checks
  that AC has a test.

## Change to an existing operation — classify it
- **Additive** (optional field, new operation): `operationId` unchanged; the consumer keeps building
  in parallel on the generated types; only deployment is ordered, producer before consumer.
- **Breaking** (removal, rename, type change): never in place — a versioning protocol (new
  versioned `operationId`/path or a version header) decided in an ADR **before** applying it.

## Procedure
1. **Collect** the operations the manifest implies (commands → writes, views → reads), each under a
   declared `operationId`.
2. **Fill the reads** from the consumer's views (`view_shape`, `consumes_rm`, `UI/`).
3. **Fill the writes** from the domain, with their declared errors.
4. **Names** from the project context-map: one concept, one name, no synonyms.
5. **Decide** each feasibility or naming conflict in an ADR (via `write-adr`, which owns format and
   the mechanical-check form).
6. **Close the loop:** every operation the boundaries imply exists in the YAML and vice versa
   (`MM lint` checks that each `operation_ids` entry resolves in `contract_path`).
7. The contract is executable only when the contract-test harness exists on **both** sides: flag it
   if missing.

## Outcome
Contract path (new or extended, with the delta), `operationId`s with their owning side, ADRs,
authorship/feasibility decisions, ambiguous requirements and unverifiable NFRs.
