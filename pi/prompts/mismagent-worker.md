---
description: "Invoke mismAgent's worker (build movement) \u2014 dispatches the mismagent-worker subagent to realize ONE building block (aggregate/application-service/port/adapter/read-model/ui/scaffold) green on its own. Normally the worker-composer dispatches it per block; use directly to build a single block."
argument-hint: "[block id / what to realize]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

Dispatch the **`mismagent-worker`** subagent (the `subagent` tool). It is **normally driven by the
worker-composer** (one worktree per block); to run it standalone give it the **block-spec** from the
manifest, the **working dir** + the side's **gate**, the **boundary interfaces** it touches, and the
**skills** (`realize-<type>` × projection + the codebase's dev-architecture memory). It returns
`READY-FOR-REVIEW | BLOCKED | BOUNCED`. See `agents/mismagent-worker.md`.
