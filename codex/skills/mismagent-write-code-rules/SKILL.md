---
name: mismagent-write-code-rules
description: "mismAgent model movement \u2014 writer of the project''s CODE-WRITING RULES as a USER-VISIBLE file: <output_dir>/code-rules.md (project-level, next to profile.md and architecture.md). Each deliberated rule carries its ENFORCEMENT CHANNEL: mechanical \u2192 the gate''s dependency/style lint (runs in the worker''s own loop + verifier step 2 + CI), discursive \u2192 a code-review criterion, structural \u2192 a citation of the owner (realize-*/seam/gates), never restated. A rule with NO channel is not written. Invoked by mismagent-architect in pass-2, after the user deliberated the rules inside ARCH_PROPOSAL and after the stack ADR (the lint choice needs the stack)."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# write-code-rules — rules that survive because something enforces them

**A coding rule exists only together with its enforcement channel** — otherwise it is a wish (the
anti-zombie principle applied to rules). You write the set the user **already deliberated** (inside
the architect's `ARCH_PROPOSAL` checkpoint); you don't invent it here.
Orientation: `methodology/mismagent.md`.

## Where the rules live — visible, next to the profile
`<output_dir>/code-rules.md` — **project-level** (NOT per-feature: rules outlive features), a
sibling of `profile.md` and `architecture.md`, so the user can open and read the whole standard.
The **profile points at it** (`code_rules:` binding) — workers and the code-review receive it
through the profile they already read: no new delivery channel. On later features the architect
proposes **deltas only**; this file stays the one source.

## The default catalogue (what the architect proposes in pass-1, inside `ARCH_PROPOSAL`)
Adapted to the stack + architecture style; the user prunes or hardens it at the checkpoint. Only
the last three rows are genuine decisions — the rest is doctrine the method already owns:

| principle | in mismAgent terms | channel |
|---|---|---|
| **SRP** | one block = one reason to change (the tactical→block map fixes the granularity) | **structural** — cite the map + `realize-*` |
| **LSP** | any adapter must pass the port's contract test unchanged | **structural** — the D2 contract test *is* LSP made executable |
| **ISP** | consumer-owned port: only the methods the consumer needs | **structural** — `realize-port` |
| **KISS / YAGNI / DRY-at-the-root** | less code, reuse the root's rule, no speculative abstraction | **structural** — the worker's frugality ladder |
| **naming = ubiquitous language** | one concept, one canonical name | **structural** — the verifier's anti-shadow check |
| **DIP / CA dependency rule** | domain + application import ONLY inward; framework/adapter imports live in the adapters | **gate lint** — a real dependency lint, config in the side's repo, wired at wave 0 |
| **error handling** | no swallowed failure; a failure crosses a boundary only as a declared shape | **gate lint** where the stack has the rule, else **review criterion** |
| **immutability** | domain values immutable by default; mutation through the root | **gate lint** where lint-able, else **review criterion** |

## The mechanical channel is the GATE, not a grep
A dependency rule is a **graph property**: POSIX grep is the wrong tool (blind to FQN use, build
files, aliases). Use the stack's **dependency lint**, named here and in the style ADR, its config
derived from `architecture.md`'s module map:
- JVM/Kotlin → **Konsist** or **ArchUnit** · TypeScript → **dependency-cruiser** or
  eslint-plugin-boundaries · Python → **import-linter** · (per stack: the architect proposes).
- The config **lives in the side's repo** (wired by the wave-0 `scaffold`, like the ui-test dep):
  it runs in the worker's own gate loop, in verifier step 2 and in CI — and on a module rename the
  worker maintains it like any build file (no ownerless rot).
- Style rules (empty-catch, mutability) join the same linter's ruleset where it has them.

## Output — `<output_dir>/code-rules.md`
One section per rule: the statement (one line), the channel, and the pointer —
`gate lint: <tool>, config <path>` · `review criterion` · `structural: <owner skill/gate>`.
Header note: *"written by the architect (model); change it only through a new deliberation — each
change cites its ADR"*. Update the **profile** (`code_rules:`) if the binding is missing.

## Consumers (why it is not a zombie)
The **user** (the visible standard), the **workers** (apply it; the gate bites in their own loop),
the **code-review** (the discursive criteria — cite the violated rule in the finding). The
mechanical rules need no reader at review time: the gate already enforced them.

## Outcome
Path of `code-rules.md`, which rules landed in the gate lint (tool + config path), which are review
criteria, which are structural citations; the profile binding set; deltas vs the existing file when
re-run on a later feature.
