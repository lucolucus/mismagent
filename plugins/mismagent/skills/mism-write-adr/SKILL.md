---
name: mism-write-adr
description: 'mismAgent''s specialized ADR writer (model movement). Produces <output_dir>/<feature>/decisions/NNNN-<slug>.md with scope/status/supersedes and — for MECHANICAL constraints — enforced_by (executable grep/lint rule that mism-verifier checks). Distinguishes mechanical ADRs (verified by the verifier) from discursive ones (verified by the code-review). Invoked by mism-create-contract, mism-architect, mism-write-infra-notes.'
---

# MismAgent — Write ADR (writer, model)

Write an Architecture Decision Record in `<output_dir>/<feature>/decisions/NNNN-<slug>.md`.
Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- ADRs with **`enforced_by`** → the `mism-verifier` runs the grep/lint rule on the diff → if the
  constraint is violated, **FAIL**. This is what makes the ADR non-zombie.
- **Discursive** ADRs (without `enforced_by`) → verified by the semantic **code-review**.
- Tasks reference them in `related_adrs` → the verifier knows which rules to apply to that task.

## Template
```markdown
---
scope: global | be | fe | sync | infra
status: proposed | accepted | superseded
supersedes: <NNNN-slug | null>
enforced_by: "<executable grep/lint rule, ONLY if the constraint is mechanical>"
---
# NNNN — <title of the decision>

## Context
<why a decision is needed; possible link to research/<topic>.md>

## Decision
<what was decided>

## Consequences
<trade-offs, what becomes binding>
```

## Rules
- **`enforced_by` ONLY for mechanical constraints** (path, identity, naming, presence/absence of a
  pattern). Example (e.g.): `"grep -rn 'DefaultAzureCredential' src/ && ! grep -rn 'ConnectionString=' src/"`.
  If the constraint requires judgment, **leave `enforced_by` empty** (the code-review verifies it).
  Do not invent non-executable rules: that would be a check that always or never fails.
- **Numbering** progressive with 4 digits; check the last number in `decisions/`.
- **`supersedes`**: if you replace an ADR, set `status: superseded` on the old one and link it.
- Breaking change of the contract → the ADR fixes the **versioning protocol** BEFORE
  applying it, **and generates** (via `mism-write-task`) a `type: cleanup` task to remove the
  old `operationId`, with `ready_when: "no-consumer-uses:<operationId>"`. So v1 does not stay
  alive forever (the contract does not rot with dead endpoints).

## Outcome
Path of the ADR, number, scope, and whether it has `enforced_by` (→ verified by the verifier) or is
discursive (→ verified by the code-review).
