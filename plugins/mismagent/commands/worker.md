---
description: Invoke mismAgent's worker (build movement) — dispatches the mismagent-worker subagent to realize ONE building block (aggregate/application-service/port/adapter/read-model/ui/scaffold) green on its own. Normally the worker-composer dispatches it per block; use directly to build a single block.
argument-hint: "[block id / what to realize]"
---

Dispatch the **`mismagent-worker`** subagent (Agent tool). It is **normally driven by the
worker-composer** (one worktree per block); to run it standalone give it the **block-spec** from the
manifest, the **working dir** + the side's **gate**, the **boundary interfaces** it touches, and the
**skills** (`realize-<type>` × projection + the side's dev-architecture + tier). It returns
`READY-FOR-REVIEW | BLOCKED | BOUNCED`. See `agents/mismagent-worker.md`.
