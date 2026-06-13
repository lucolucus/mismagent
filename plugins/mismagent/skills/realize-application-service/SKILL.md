---
name: realize-application-service
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes a thin command/use-case (Application Service) — does NOT re-implement an aggregate's rule: it goes through the root that owns it (previous block) and reads the other context ONLY via the port's interface. AC-test with a fake port. 'Green on its own' includes that the Aggregate's invariant-tests stay green. Loaded by the worker when block.type = application-service.
---

# realize-application-service — the thin use-case, does not duplicate the rule

You realize **ONE command/use-case** (an Application Service). It is **thin**: it orchestrates, it
owns no rules. Rationale: `redesign/composer-spec.md` §1·§4.3.

## The pattern
- **You do not duplicate the rule: you go through the owner.** You go through the **Aggregate root**
  that owns the invariant (block built earlier), you do **not** rewrite it. If you call a root to
  mutate, the invariant is its.
- **Read the other context ONLY via the Port** (consumer-owned interface, in primitives). Never the
  other context's source, never its domain types — only the port's signature.
- **No domain decision in the service:** if you catch yourself evaluating a raw field (e.g.
  `attivo == true`), it is a **bounce**: the decision is a predicate of the root/port (`vendibile`),
  not yours.
- Stay **mute on the how** of persistence: write via the repository/adapter, do not touch the DB
  directly.

## The check (you carry it with you)
- **AC-test with a fake port:** you verify the use-case's behavior using a **fake** of the port (green
  on its own, without the real other side). The real-on-real welding is done by the Composer in D2.
- **Translate the user's `tests_nl`** (§16) into the use-case's AC-tests.
- **Green on its own includes the Aggregate's invariant-tests:** if your use-case breaks a root
  invariant, you are not green. The invariant tests of the owner block remain your safety net.

## TDD + green on its own
`tdd` red-green-refactor. Self-review fix-loop: run the **side's gate** and re-read the diff against
every AC, until green and every AC covered.

## Return (to the worker)
`BOUNDARY_HONORED`: did you call the root instead of re-deciding? did you read the other side only via
the port? yes/no.
