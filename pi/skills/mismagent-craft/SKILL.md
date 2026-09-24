---
name: mismagent-craft
description: "mismAgent build: the XP inner loop (red, green, refactor) with on-demand references, each read only for the concrete problem seen. Loaded once by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# craft

Per acceptance criterion:
1. **RED** — one failing test from the criterion → `references/tdd.md` when choosing/diagnosing a test.
2. **GREEN** — the minimum that passes → `references/frugality.md` when choosing reuse/dependency/abstraction.
3. **REFACTOR** — only the code this change touched, tests green → `references/simple-design.md` to judge; then, for the concrete obstacle: `references/clean-code.md` (names/flow/comments) · `references/solid.md` (responsibilities/dependencies/substitutability) · `references/refactoring.md` (safe transformation).
   Exit: obstacle removed, tests green, obligations met. No obstacle → no change; another aesthetic preference does not reopen the loop.
4. Next criterion.

Read a reference only for a problem you see, never by block type. The project's `code-rules.md` narrows, extends or overrides these heuristics: deliberate rules win, never over contracts, boundaries or security.
