---
description: Launch mismAgent's read-only board — a live, lightweight localhost view of a feature's building blocks and their state (which folder: todo/doing/done) + each block's Cosa fare / Task. Reads the rich derived block files (blocks/<ctx>/{todo,doing,done}/<id>.md); NEVER writes. Use during build to watch progress.
argument-hint: "[feature | <output_dir>/<feature>/ | project root]"
---

Launch the **read-only board** for `$ARGUMENTS` (or the current project / feature). It is a zero-dep
Python stdlib server that scans `blocks/<ctx>/{todo,doing,done}/<id>.md` and serves a live kanban; it
**never writes** the block files or moves state (only the worker-composer does that).

Run it **in the background** and tell the user the URL it prints:

```
python3 "$CLAUDE_PLUGIN_ROOT/tools/board.py" <feature-dir-or-project-root>
```

- `<feature-dir>` = `<output_dir>/<feature>/` (e.g. `.mismagent/cassa`). If you pass the **project
  root** (or omit it) and there is a single feature under `.mismagent/`, the board auto-resolves it;
  with several, pass one explicitly.
- It prints `http://127.0.0.1:<port>` — surface that to the user (status updates live, polling every
  ~1.5s). Stop it with Ctrl-C (or kill the background process).

See `tools/board.py`.
