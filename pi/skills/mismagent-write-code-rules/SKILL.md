---
name: mismagent-write-code-rules
description: "mismAgent model: writes the project's <output_dir>/code-rules.md \u2014 each deliberated coding rule with its enforcement channel (gate lint, review criterion or structural owner); a rule with no channel is not written. Invoked by the architect in pass 2."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# write-code-rules — rules that survive because something enforces them

**A coding rule exists only together with its enforcement channel** — otherwise it is a wish. You
write the set the user **already deliberated** (the architect's `ARCH_PROPOSAL`); you don't invent it.
Orientation: `methodology/mismagent.md`.

## Where the rules live — visible, next to the profile
`<output_dir>/code-rules.md` — **project-level** (rules outlive features), beside `profile.md` and
`architecture.md`. The **profile points at it** (`code_rules:`): workers and the code-review
receive it through the profile. Later features propose **deltas only**; this file is the one source.

## The default catalogue (proposed in pass-1, inside `ARCH_PROPOSAL`)
Adapted to the stack; the user prunes or hardens it. The
principles are **heuristics** (the `craft` skill's references: `solid.md`, `clean-code.md`,
`frugality.md`); a row becomes an **obligation** only when written here with its channel.
Deliberate rules win over the generic heuristics, never over contracts, boundaries or security.

| principle | in mismAgent terms | channel |
|---|---|---|
| **SRP** | the tactical→block map sets the granularity; one block does not by itself prove SRP | **structural** — the map + `realize-*` |
| **OCP** — only where a variation is required or demonstrated | an extension point isolates that variation; none speculative | **review criterion** |
| **LSP** | an adapter passes the port's contract test unchanged — executable evidence for the cases it covers | **structural** — the port's contract test |
| **ISP** | consumer-owned port: only the methods the consumer needs | **structural** — `realize-port` |
| **KISS / YAGNI / DRY-at-the-root** | less code, reuse the root's rule, no speculative abstraction | **structural** — the worker's frugality |
| **naming = ubiquitous language** | one concept, one canonical name | **structural** — the verifier's anti-shadow check |
| **CA dependency rule** (a concretization, not a synonym, of DIP) | domain + application import ONLY inward; framework/adapter imports live in the adapters | **gate lint** — a dependency lint, config in the side's path, wired at wave 0 |
| **error handling** | no swallowed failure; a failure crosses a boundary only as a declared shape | **gate lint** where the stack has the rule, else **review criterion** |
| **immutability** | domain values immutable by default; mutation through the root | **gate lint** where lint-able, else **review criterion** |

## The mechanical channel is the GATE, not a grep
A dependency rule is a **graph property**: a text search is the wrong tool (blind to qualified
names, build files, aliases). Use the stack's **dependency lint**, named here and in the style
ADR, its config derived from `architecture.md`'s module map:
- The config **lives in the side's path** (wired by the wave-0 `scaffold`): it runs in the
  worker's gate loop, verifier step 2 and CI; on a module rename the worker maintains it.
- Style rules (empty-catch, mutability) join the same linter's ruleset where it has them.
- **This is the ADR checks' mechanism:** the style ADR's `enforced_by` names the lint config as its
  `check` (see `write-adr`) — one mechanism, same fixtures and result; no second grep.

## Output — `<output_dir>/code-rules.md`
One section per rule: the statement (one line), its **scope** (where it applies), a verifiable
criterion, the channel and the pointer — `gate lint: <tool>, config <path>` · `review criterion` ·
`structural: <owner skill/gate>` — and its **exceptions**, each citing its ADR.
Header note: *"written by the architect (model); change it only through a new deliberation — each
change cites its ADR"*. Update the **profile** (`code_rules:`) if the binding is missing.

## Consumers (why it is not a zombie)
The **user** (the visible standard), the **workers** (the gate bites in their loop), the
**code-review** (the discursive criteria, cited in the finding); mechanical rules need no reviewer.

## Outcome
Path of `code-rules.md`, which rules landed in the gate lint (tool + config path), which are review
criteria, which are structural citations; the profile binding set; deltas vs the existing file on a
later feature.
