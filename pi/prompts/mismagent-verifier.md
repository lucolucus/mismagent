---
description: "Invoke mismAgent's structural verifier (build movement) \u2014 dispatches the mismagent-verifier subagent with FRESH CONTEXT to re-run build+test+contract-test, check enforced_by, and that every AC has a test. Returns PASS|FAIL|SKIP. Normally the worker-composer dispatches it (D1); use directly to verify one block/branch."
argument-hint: "[repo/worktree path + branch + block-spec]"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.
> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);
> call it with `agentScope: "both"` so the `.pi/agents/` definitions are visible.

Dispatch the **`mismagent-verifier`** subagent (the `subagent` tool, **fresh context**). It is **normally driven
by the worker-composer** (Phase 3 / D1); to run it standalone give it the **repo/worktree path**, the
`BRANCH` and `BASE` for the diff, and the **block-spec** (ACs, the boundary it honors,
`related_adrs`). Read-only → returns `PASS | FAIL | SKIP`. See `agents/mismagent-verifier.md`.
