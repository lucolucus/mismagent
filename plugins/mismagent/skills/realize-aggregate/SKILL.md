---
name: realize-aggregate
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes an Aggregate root + value objects — the block that OWNS the rule: invariants live HERE, written and tested once (invariant-test, one per invariant). State with private setters, invariant_fields confined (named predicate exposed, not the raw field), no deletion (soft-delete). Primitive/Published Language identity at the boundary, value class internal only. Carries the §14 gate (invariant-bearing state captive of the root). Loaded by the worker when block.type = aggregate.
---

# realize-aggregate — the Aggregate owns the rule

You realize **ONE Aggregate root** (+ its value objects). It is the **owner of the intra-context
boundary**: invariants live here, written **once**. Application Services lean on them, they do not
copy them. Rationale: `redesign/composer-spec.md` §1·§9·§14.

## The pattern
- **Pure domain:** no dependency on DB/framework. The invariants must hold in ms, without persistence
  (persistence is a separate `realize-adapter`).
- **State with private setters:** no mutation except via a **method of the root**. That is where the
  invariant lives.
- **`invariant_fields` confined:** the fields that embody an invariant are `private`/`private set`.
  Expose the **named predicate** (e.g. `vendibile`), **never** the raw field (e.g. `attivo`).
  Consumers ask for the predicate, they do not re-decide from the field.
- **No deletion method:** soft-delete (the state is a confined flag), never a physical `delete`.
- **Identity:** at the **boundary** it is **primitive / Published Language** (e.g. `Int`, or a
  shared-kernel); the `value class`/strong identity type lives **only inside** the context (you do not
  export it to the consumer — it would recreate a coupling on your domain).

## The check (you carry it with you)
- **Invariant-test: one per invariant** declared in the block-spec (`invariants`). They are the
  **contract test of the intra**: the Aggregate's boundary is welded when these stay green.
- **Translate the user's `tests_nl`** (§16) into these invariant-tests: the sentence *"I cannot sell a
  deactivated product"* → a test that encodes INV-…; the test is the **encoding** of their intent, not
  an invention of yours.

## The §14 gate (you bring it respected, the verifier checks it)
Invariant-bearing state is **captive of the root**:
1. invariant-bearing properties `private set`/init-only → no one outside mutates the state;
2. `invariant_fields` fields (e.g. `Attivo`) referenced **only inside** the Aggregate → no
   re-deciding from raw reads; consumers use the named predicate.
(Rule 1 on persistence — no `INSERT/UPDATE/DELETE` from outside — is honored by the `realize-adapter`.)

## TDD + green on its own
`tdd` red-green-refactor. Self-review fix-loop: run the **side's gate** (profile) and re-read the diff
against every invariant, until green and every invariant covered.

## Return (to the worker)
`PUBLIC_API`: the public signatures of the root + the **named predicate** that consumers will use
(for an aggregate this IS the boundary another block will use).
