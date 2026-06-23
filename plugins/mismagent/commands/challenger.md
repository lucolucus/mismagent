---
description: Invoke mismAgent's challenger (explore movement) — dispatches the mismagent-challenger subagent with FRESH CONTEXT to try to DEMOLISH the idea before it is modeled. Read-only; returns KILL | RESHAPE | PROCEED with the sharpest objections. Use early in explore (and optionally on the draft model).
argument-hint: "[the idea / what to attack]"
---

Dispatch the **`mismagent-challenger`** subagent (Agent tool, **fresh context**) on `$ARGUMENTS` (or the
current idea/model). It is read-only and returns a **`KILL | RESHAPE | PROCEED`** verdict: on `KILL`
stop and report to me; on `RESHAPE` redesign with me; on `PROCEED` close the
`MUST_ANSWER_BEFORE_MODELING` items before going on. See `agents/mismagent-challenger.md`.
