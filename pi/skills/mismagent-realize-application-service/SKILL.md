---
name: mismagent-realize-application-service
description: "mismAgent worker block-type skill for `application-service`. Realizes a thin use-case that goes through the owning root and reads other contexts only via their port; AC tests with a fake port. Loaded by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-application-service — the thin use-case

You realize **one command/use-case**. It orchestrates; it owns no rule.

## The pattern
- **Go through the owner:** state changes happen by calling the Aggregate root that owns the
  invariant (built in an earlier block) — never by assigning its fields or rewriting its rule.
- **Other contexts only via their port**, in its Published Language — never their source or their
  domain types.
- **No domain decision here:** evaluating a raw invariant field (e.g. `active == true`) is a bounce —
  the decision is a predicate of the root or port.
- **Persistence through the repository/adapter**, never the database directly.

## The check you carry
- **AC tests with a fake port** — green on its own; the real weld is D2.
- **Translate the user's `tests_nl`** into the AC tests, with a rejection/failure case per command.
- **Green includes the owner's invariant tests:** breaking a root invariant means not green.

## TDD, green on its own
Red-green-refactor. Run the side's gate and re-read the diff against every AC until green and every
AC covered.

## Return
`BOUNDARY_HONORED`: went through the root instead of re-deciding? read other contexts only via the
port? yes/no.
