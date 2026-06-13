# Attic — mismAgent's superseded pieces

Components of the **file-driven** flow (pre-Composer), kept out of the plugin **on purpose**:
they do not enter the Claude Code registry, so no agent can invoke them by mistake — a loaded
superseded piece is a zombie in waiting. The full history is kept by `git log`.

| piece | superseded by |
|---|---|
| `commands/dev-orchestrator-v2.md` | `/mismagent:composer` (architecture-driven build) |
| `commands/project-orchestrator.md` | the Composer model (multi-feature = projection of the boundaries, not epics) |
| `skills/mism-build-dag/` | `mism-build-manifest` (the model→build bridge is the manifest, not a dag.yaml of file-tasks) |
| `skills/mism-dev-story-lean/` | the worker's `realize-*` × `seam-*` skills |
| `agents/mism-developer-lean.md` | `mism-worker` (realizes building blocks, not file-lists) |
| `methodology/mism-dag.md` | `methodology/mismagent.md` + `redesign/composer-spec.md` |

Redesign rationale: `plugins/mismagent/redesign/composer-spec.md` and the first adoption project's
`MISMAGENT-LOG.md` (entries #16 and "REVIEW + FIX BATCH").
