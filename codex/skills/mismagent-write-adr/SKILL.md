---
name: mismagent-write-adr
description: "mismAgent''s specialized ADR writer (model movement). Produces <output_dir>/<feature>/decisions/NNNN-<slug>.md with scope/status/supersedes and \u2014 for MECHANICAL constraints \u2014 enforced_by (executable grep/lint rule that mismagent-verifier checks). Distinguishes mechanical ADRs (verified by the verifier) from discursive ones (verified by the code-review). Invoked by create-contract, mismagent-architect, write-infra-notes."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

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
# a bare string = kind: prohibition ("must find nothing"). A PRESENCE rule ("must exist") uses the
# structured form — it is WAVE-GATED on the block that satisfies it:
# enforced_by:
#   kind: presence
#   rule: "<executable grep/lint>"
#   exigible_from: <block-id>   # from the manifest: the block owning the symbol; the verifier
#                               # enforces the rule only once that block is merged
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
- **…and SHELL-PORTABLE — the rule is executed via `bash -c '<exact string>'`** (friction-log-4
  #30/#37/#49): quote every glob (`--include='*.kt'` — unquoted, zsh errors or expands it) and
  every expansion (`":${m}:"` — an unquoted `:$m:` trips zsh's history/glob modifiers), no
  undeclared bash-only constructs. Validate by executing the EXACT frontmatter string via
  `bash -c '<string>'` — the way the verifier runs it — never by retyping it in an interactive
  shell (aliases/`ugrep` wrappers give false verdicts). A rule whose verdict changes with the
  shell is not mechanical.
- **Two kinds of rule — prohibition and presence; presence is WAVE-GATED** (friction-log-4 #19).
  A *prohibition* ("this grep must find nothing") is exigible from wave 0 forever — the bare-string
  form implies it. A *presence* ("this construct MUST exist") is red **by construction** until the
  block that satisfies it lands: write it in the structured form (`kind: presence` +
  `exigible_from: <block-id>`, the manifest block owning that symbol) so the verifier enforces it
  only once that block is merged. An ungated presence rule stays red for half the build about a
  block nobody has built yet — a failure that tells its recipient nothing, and teaches everyone to
  ignore the verifier.
- **A presence rule anchors to a CODE CONSTRUCT, never a bare name** (friction-log-4 #37): match a
  declaration / import / type-use (`class NetworkEscPos`, `: StampaBigliettoPort`, an `import`
  line), never a name a KDoc or a test fixture can *mention* — a presence grep green on a comment
  green-lights a block that does not exist (a false green hiding unbuilt work).
- **Comment-strip EVERY grep that scans code — prohibition AND presence** (friction-log-4 #35/#37).
  A prohibition that doesn't exclude comments turns the prose documenting the rule into a
  violation (the worker rewrites honest KDoc to appease the grep); a presence that counts comments
  is the false green above. Apply one uniform idiom (e.g. after `grep -rn`, drop comment lines
  with `grep -vE '^[^:]*:[0-9]+:[[:space:]]*(//|\*|/\*)'` — adjust the tokens to the stack) — or state
  in the ADR that prose may not name the symbol. Two sibling rules where one strips and one
  doesn't is an incoherence workers pay for.
- **Ask: "what OTHER ways to violate this does the rule NOT catch?"** (friction-log-4 #26) before
  shipping any `enforced_by` — enumerate the idiomatic alternatives, cover the set, then scope the
  rule to the modules where the discipline applies. Cautionary tale: a no-wall-clock rule grepping
  only `System.currentTimeMillis` while `Instant.now()` / `Clock.systemUTC()` /
  `LocalDateTime.now()` pass untouched. A guard covering ONE violation path is worse than no
  guard: it promises a discipline it doesn't enforce.
- **An ADR that elects a field as a KEY implies a UNIQUENESS invariant** (friction-log-4 #43): if
  the decision uses a field as a lookup/correlation/decode key (a per-version compact index, a
  correlation id), the aggregate publishing it must carry the matching uniqueness invariant
  (`[INV-n]` + its test) — name it in the ADR and check it exists in the model/manifest, or record
  explicitly why it holds by construction. A key-electing ADR without its uniqueness invariant is
  a mechanically detectable gap: the decode is ambiguous exactly when it matters.
- **Validate every rule on a fixture — positive AND negative** before committing it: it must FAIL on
  a snippet that violates the constraint and PASS on one that satisfies it (run both via
  `bash -c`, as above). A rule that can't be made
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
- **…and with the PROFILE's boundary rules** (friction-log-4 #18): check the decision's
  *mechanism* against them too. An ADR whose guardian collides with a profile rule — the canonical
  case: a migration-verify tool that requires a **committed snapshot `.db`** vs the profile's
  "never commit DB files", so the `.gitignore` silently drops the guardian's input and the ADR
  runs unguarded forever — is a **collision to surface as a decision** (scope an explicit
  exception into the profile rule, or renounce the mechanism and record that the ADR has no
  mechanical guardian). Never leave it for a worker to trip over at wave 0: two authoritative
  artifacts contradicting each other is the #9 family, on the profile axis.
- Breaking change of the contract → the ADR fixes the **versioning protocol** BEFORE
  applying it, **and generates** (via `write-task`) a `type: cleanup` task to remove the
  old `operationId`, with `ready_when: "no-consumer-uses:<operationId>"`. So v1 does not stay
  alive forever (the contract does not rot with dead endpoints).

## Outcome
Path of the ADR, number, scope, and whether it has `enforced_by` (→ verified by the verifier) or is
discursive (→ verified by the code-review).
