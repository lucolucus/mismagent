---
name: mismagent-readiness-gate
description: "mismAgent optional pre-flight before the build: runs the tool's `lint` on a feature and reports gaps with where to bounce them. The authoritative gate stays the worker-composer's readiness step. Use to check a feature is ready."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# mismAgent — Readiness pre-flight (model → build)

A thin, optional early run of the worker-composer's readiness step. Its verdict is not persisted:
the one gate lives in the worker-composer.

## Run
`MM lint <output_dir>/features/<feature>/`, where `MM` = `python3 "@@MISMAGENT_SKILLS@@/mismagent-worker-composer/scripts/mismagent.py"`.
It prints `{ok, gaps:[{rule, where, gap, bounce_to}], deferred}` — structural checks only (the list:
`@@MISMAGENT_SKILLS@@/mismagent-worker-composer/references/CLI.md`). Judgment items (a high-value block with no `tests_nl`, the
gate's red-green proof, stale spikes) you only **name** as reminders.

## Outcome
- **PASS** (`ok: true`) → say so and launch `/skill:mismagent-worker-composer <feature>`.
- **BLOCKED** → each gap with its `where` and `bounce_to`.
- **PENDING** → `deferred` ADR checks (not yet due), parked blocks
  (`open-questions/<block-id>.md`), open spike nodes — listed separately, not errors.
