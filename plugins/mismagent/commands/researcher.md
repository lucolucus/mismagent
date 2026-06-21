---
description: Invoke mismAgent's researcher (explore movement) — dispatches the mismagent-researcher subagent to explore a domain/topic and gather material into research/<topic>.md. Use only when a decision needs investigation AND the topic unblocks something downstream.
argument-hint: "[topic / question to research]"
---

Dispatch the **`mismagent-researcher`** subagent (Agent tool) on `$ARGUMENTS`. Frame what it unblocks
downstream (a decision by the analyst? an ADR?); if nothing → it returns `NEEDS-SCOPE` and writes
nothing. Output: `research/<topic>.md`, cited later by an ADR. See `agents/mismagent-researcher.md`.
