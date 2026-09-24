---
description: "mismAgent build: dispatch the mismagent-worker subagent to realize ONE building block green on its own. The worker-composer normally dispatches it per block; use directly to build a single block."
argument-hint: "[block id / what to realize]"
---

Dispatch the **`mismagent-worker`** subagent (Agent tool). The worker-composer normally drives it
(one worktree per block); standalone, give it the block's `MM pack`, the **working dir** + the
side's **gate**, and the **skills** (`realize-<type>` + the codebase's
dev-architecture memory). It returns `READY-FOR-REVIEW | BLOCKED | BOUNCED`. See
`agents/mismagent-worker.md`.
