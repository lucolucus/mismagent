---
description: "mismAgent build: dispatch the mismagent-worker subagent to realize ONE building block green on its own. The worker-composer normally dispatches it per block; use directly to build a single block."
argument-hint: "[block id / what to realize]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md, Setup);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

Dispatch the **`mismagent-worker`** subagent (the `subagent` tool). The worker-composer normally drives it
(one worktree per block); standalone, give it the block's `MM pack`, the **working dir** + the
side's **gate**, and the **skills** (`realize-<type>` × projection + the codebase's
dev-architecture memory). It returns `READY-FOR-REVIEW | BLOCKED | BOUNCED`. See
`agents/mismagent-worker.md`.
