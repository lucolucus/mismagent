---
name: mismagent-readiness-gate
description: "mismAgent pre-flight before the build \u2014 an OPTIONAL early run of the worker-composer''s readiness step, to catch an incomplete manifest before launching. It runs the deterministic tool''s `lint` and reports; it has no checklist of its own. Use it to check a feature is ready, or just launch the worker-composer and let its readiness step do it."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# MismAgent — Readiness pre-flight (model → build)

A **thin, optional pre-check** of the worker-composer's readiness step, run *early*. **Ephemeral**
verdict (not persisted). There is **one** gate, and it lives in the worker-composer.

## Run
`MM lint <output_dir>/features/<feature>/`, where `MM` = `python3 .agents/skills/mismagent-worker-composer/scripts/mismagent.py`.
It prints `{ok, gaps:[{rule, where, gap, bounce_to}], deferred}` — exact structural checks only
(the list: `.agents/skills/mismagent-worker-composer/references/CLI.md`). The judgment items (a high-value block with no
`tests_nl`, the gate's red-green proof, stale spikes) you only **name** as reminders — the
worker-composer settles them.

## Outcome
- **PASS** (`ok: true`) → say so and launch `$mismagent-worker-composer <feature>`.
- **BLOCKED** → report each gap with its `where` and its `bounce_to` (the step to rework).
- **EXPLICIT PENDING** → `deferred` contract files (a wave-0 scaffold output), a parked block
  (`open-questions/<block-id>.md`), an open `type: spike` node: list them separately — neither
  actionable nor an error.
