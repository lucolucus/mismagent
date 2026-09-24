---
name: mismagent-realize-aggregate
description: "mismAgent worker block-type skill for `aggregate`. Realizes an Aggregate root + value objects that own the invariants \u2014 one invariant test each, state captive of the root, named predicates exposed. Loaded by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-aggregate — the Aggregate owns the rule

You realize **one Aggregate root** and its value objects. Invariants live here, written once;
application services go through the root, they never copy the rule.

## The pattern
- **Pure domain:** no database or framework dependency; invariants hold in milliseconds without
  persistence (persistence is a `realize-adapter` block).
- **Identity:** at the boundary it is the Published Language type pinned in the manifest (a
  primitive or a shared-kernel VO); a strong identity type stays inside the context.
- **Deletion follows the domain:** if the model says a record is never physically removed, deletion
  is a state change of the root (e.g. a confined flag), never a physical delete.

## The confinement guarantees — invariant-bearing state is captive of the root
1. **Persistent writes only in the adapter:** nothing outside this aggregate's persistence adapter
   inserts, updates or deletes its tables.
2. **State mutations only through the root:** invariant-bearing properties have no public setter
   (private or init-only); the only way to change them is a method of the root, where the invariant
   is checked.
3. **Reads through predicates:** the `invariant_fields` are referenced only inside the aggregate;
   the root exposes a **named predicate** (e.g. `sellable`) and consumers ask it instead of
   re-deciding from the raw field.

The manifest turns these into check references on the aggregate's ADR (`enforced_by`); the gate runs
them and the verifier reads the result. They prove state is confined, not that a rule exists only
once — a parallel predicate that never touches the confined fields is for the code review.

## The check you carry
- **One invariant test per declared invariant**; they are the aggregate's contract test.
- **Translate the user's `tests_nl`** into those tests — they encode the user's intent, not yours.
- **Test names start with the invariant tag `INV-n `** — no brackets or other characters illegal in
  the stack's test names — so per-block coverage is matched mechanically.
- **A concurrency claim needs a real contention test:** an invariant or AC that says "under
  concurrency" / "simultaneous" is proven by N concurrent callers released together against the same
  instance, failing before the synchronization lands and passing after — never by sequential calls.
  The root exposes an atomic all-or-nothing operation, never a check-then-act the caller composes,
  and returns an outcome value instead of crashing where the outcome is expected.

## TDD, green on its own
Red-green-refactor. Run the side's gate and re-read the diff against every invariant until green and
every invariant covered.

## Return
`PUBLIC_API`: the root's public signatures and the named predicates consumers will use.
