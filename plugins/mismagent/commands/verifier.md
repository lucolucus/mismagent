---
description: "mismAgent build: dispatch the mismagent-verifier subagent (fresh context, read-only) on one block — gate, AC coverage, contracts, ADR checks. Returns PASS|FAIL|SKIP. The worker-composer normally runs it; use directly for one block."
argument-hint: "[repo/worktree path + branch + block-spec]"
---

Dispatch the **`mismagent-verifier`** subagent (Agent tool, **fresh context**). The worker-composer
normally drives it; standalone, give it the **repo/worktree path**, the `BRANCH`, the `RANGE` and
`HEAD_SHA` from `MM diff-range`, and the block's `MM pack`. Read-only → `PASS | FAIL | SKIP`; an objection to a `D-NNNN` goes into that entry's `Debate`
(`F/decisions.md`). See
`agents/mismagent-verifier.md`.
