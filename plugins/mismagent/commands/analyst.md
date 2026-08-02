---
description: Invoke mismAgent's analyst (explore movement) — dispatches the mismagent-analyst subagent to model the STRATEGIC domain (bounded contexts + relationships), fix the UBIQUITOUS LANGUAGE (amending the PROJECT context-map.md, never re-forking it) and the Seeds for the tactical (written to the feature's tactical-model.md). Use in explore after the idea survives the challenger.
argument-hint: "[what survived / domain notes]"
---

**Re-entrance guard:** if the project's `<output_dir>/context-map.md` **already covers this
feature's contexts**
(bounded contexts + ubiquitous language), do not re-model from scratch — say so and ask what to
extend or reopen (a new context? a name to re-fix?), then dispatch with that named scope
(friction-log-4 #14).

Otherwise dispatch the **`mismagent-analyst`** subagent (Agent tool) on `$ARGUMENTS` (or what survived the
challenger), **passing it the existing `<output_dir>/context-map.md` as authoritative** when one
exists: it **amends** that map — adds the contexts and terms this feature introduces, reuses the
rest verbatim — and never starts a second one. Fix with me the **ubiquitous language** (one concept = one canonical name). On
`NEEDS-INPUT` bring the `AMBIGUITIES` to me and re-dispatch. Output: the project `context-map.md` (strategic) + the feature's `tactical-model.md` (seeds) (
ubiquitous language + Seeds for the tactical). See `agents/mismagent-analyst.md`.
