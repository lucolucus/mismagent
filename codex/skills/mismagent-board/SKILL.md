---
name: mismagent-board
description: "Launch mismAgent's read-only board \u2014 a live, lightweight localhost view of a feature's building blocks and their state (which folder: todo/doing/done) + each block's What to do / Tasks. Reads the rich derived block files (blocks/<ctx>/{todo,doing,done}/<id>.md); NEVER writes. Use during build to watch progress."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

Launch the **read-only board** for `<the argument this skill was invoked with>` (or the current project / feature). It is a zero-dep
Python stdlib server that scans `blocks/<ctx>/{todo,doing,done}/<id>.md` and serves a live kanban; it
**never writes** the block files or moves state (only the worker-composer does that).

Run it **in the background** and tell the user the URL it prints:

```
python3 .agents/skills/mismagent-board/scripts/board.py <feature-dir-or-project-root>
```

- `<feature-dir>` = `<output_dir>/features/<feature>/` (e.g. `.mismagent/features/cassa`). If you pass
  the **project root** (or omit it) and there is a single feature under `<output_dir>/features/`, the
  board auto-resolves it; with several, pass one explicitly. The project trunk (`profile.md`,
  `context-map.md`, `decisions/`, …) is never mistaken for a feature: only `features/` is scanned.
- It prints `http://127.0.0.1:<port>` — surface that to the user (status updates live, polling every
  ~1.5s). Stop it with Ctrl-C (or kill the background process).

See `tools/board.py`.
