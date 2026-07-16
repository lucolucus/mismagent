---
name: write-adr
description: 'mismAgent''s specialized ADR writer (model movement). Produces <output_dir>/<feature>/decisions/NNNN-<slug>.md with scope/status/supersedes and — for MECHANICAL constraints — enforced_by (executable grep/lint rule that mismagent-verifier checks). Distinguishes mechanical ADRs (verified by the verifier) from discursive ones (verified by the code-review). Invoked by create-contract, mismagent-architect, write-infra-notes.'
---

# MismAgent — Write ADR (writer, model)

Write an Architecture Decision Record in `<output_dir>/<feature>/decisions/NNNN-<slug>.md`.
Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- ADRs with **`enforced_by`** → the `mismagent-verifier` runs the grep/lint rule on the diff → if the
  constraint is violated, **FAIL**. This is what makes the ADR non-zombie.
- **Discursive** ADRs (without `enforced_by`) → verified by the semantic **code-review**.
- Blocks reference them in `related_adrs` → the verifier knows which rules to apply to that block.

## Template
```markdown
---
scope: global | be | fe | sync | infra
status: proposed | accepted | superseded
supersedes: <NNNN-slug | null>
closes_spike: <spike-slug | null>   # the context-map "Open spikes" entry this ADR answers, if any
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
- **`enforced_by` greps are CODE-scoped, never TEXT-scoped** (friction-log #11). Anchor to
  **import/dependency statements** or **identifiers in expression context**, never a bare token — a
  doc-comment that *names* the forbidden tech (the clearest documentation) must not trip the gate.
  Forbidden-tech absence → match the import (`! grep -rEn '^\s*import .*(ktor|okhttp|retrofit)' <dir>/`),
  not `! grep 'OpenAPI'` over raw text; a confined field → match its access in code, **excluding
  comment lines** (the comment syntax comes from the stack).
- **Target DIRS/PACKAGES or SYMBOLS, never a guessed filename** (friction-log #12). The file layout
  is the **worker's** choice — it may name the class `FooSqlDelight.kt`, not `Foo.kt`. A grep pinned
  to a non-existent filename **matches nothing and looks green** (a false-green, worse than a
  failure). Scope the target to a package/dir (`.../persistenza/`) or a symbol; the verifier FAILs a
  rule whose target path does not exist.
- **Greps must be POSIX-PORTABLE** (friction-log #3). The `enforced_by` rule runs on whatever `grep`
  the machine has (BSD/macOS *and* GNU/Linux). **Avoid GNU-only extensions** — no `grep -z`
  (multiline/NUL match), no `-P` (PCRE), no `\d`/`\b`-style PCRE classes; stick to BRE/ERE
  (`grep -rEn`), POSIX classes (`[[:space:]]`), and per-line matching. If a constraint truly needs a
  multiline match, express it as two single-line greps combined with `&&`/`!` instead of `-z`.
- **Validate every rule on a fixture — positive AND negative** before committing it: it must FAIL on
  a snippet that violates the constraint and PASS on one that satisfies it. A rule that can't be made
  to fail (or can't be made to pass) is a false-green/false-red — do not ship it. *(The architect
  already does this spontaneously; make it part of the protocol.)*
- **Numbering** progressive with 4 digits; check the last number in `decisions/`.
- **`supersedes`**: if you replace an ADR, set `status: superseded` on the old one and link it.
- **An ADR that ANSWERS an open spike closes it — in BOTH directions** (friction-log-4 #13). If the
  decision satisfies a spike's closure criterion (context-map "Open spikes", or a `type: spike`
  node), set **`closes_spike: <spike-slug>`** in the frontmatter AND mark the spike **`[x]`** in the
  context-map (and close its materialized node, if one exists) in the same pass. A spike whose
  criterion an ADR satisfies but that stays `[ ]` open is a stale artifact: the human reader — and
  every future feature that cites the map — will re-open a settled question.
- **Reconcile with the context-map BEFORE finalizing** (friction-log-4 #9). Grep the context-map for
  the decision's subject: a line that contradicts the ADR (e.g. a tactical note still deferring, or
  asserting, what this ADR just decided otherwise) must be **updated** — or the supersede recorded
  there — in the same pass. An ADR and a context-map that disagree in silence are two sources of
  truth; no downstream step re-aligns them for you.
- Breaking change of the contract → the ADR fixes the **versioning protocol** BEFORE
  applying it, **and generates** (via `write-task`) a `type: cleanup` task to remove the
  old `operationId`, with `ready_when: "no-consumer-uses:<operationId>"`. So v1 does not stay
  alive forever (the contract does not rot with dead endpoints).

## Outcome
Path of the ADR, number, scope, and whether it has `enforced_by` (→ verified by the verifier) or is
discursive (→ verified by the code-review).
