---
name: craft
description: 'mismAgent build: the XP inner loop (red, green, refactor) with on-demand references, each read only for the concrete problem seen. Loaded by the builder; the review table by the reviewer and the architect.'
user-invocable: false
---

# craft

Per acceptance criterion:
1. **RED** — one failing test from the criterion → `references/tdd.md` when choosing/diagnosing a test.
2. **GREEN** — the minimum that passes → `references/frugality.md` when choosing reuse/dependency/abstraction.
3. **REFACTOR** — only the code this change touched, tests green → `references/simple-design.md` to judge; then, for the concrete obstacle: `references/clean-code.md` (names/flow/comments) · `references/solid.md` (responsibilities/dependencies/substitutability) · `references/refactoring.md` (safe transformation).
   Exit: obstacle removed, tests green, obligations met. No obstacle → no change; another aesthetic preference does not reopen the loop.
4. Next criterion.

Read a reference only for a problem you see. The project's `ARCHITECTURE.md` (layering, error policy) and its `conventions` skill (how code is written there, the model slice) narrow or override these heuristics: their decisions win. `references/review-table.md` is how the code will be reviewed.
