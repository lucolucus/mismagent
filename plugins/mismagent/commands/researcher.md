---
description: Dispatch mismAgent's researcher (explore) to gather material into research/<topic>.md. Use only when a downstream decision needs investigation.
argument-hint: "[topic / question to research]"
---

Dispatch the **`mismagent-researcher`** subagent (Agent tool) on `$ARGUMENTS`. Frame what it unblocks
downstream (a decision by the analyst? an ADR?); if nothing → it returns `NEEDS-SCOPE` and writes
nothing. Output: `research/<topic>.md`, cited later by an ADR. See `agents/mismagent-researcher.md`.
