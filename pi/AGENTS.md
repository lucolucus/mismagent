# mismAgent — pi packaging

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

> **pi mapping (this packaging).** `[skill]`/`[command]` steps are pi **skills** — invoke with `/skill:mismagent-<name>` (pi also loads them on demand; names carry the `mismagent-` prefix because pi's skill space is flat). `[agent]` steps are **prompt templates** (`/mismagent-<name>`) that dispatch the matching subagent definition in `.pi/agents/` through the `subagent` tool (`agentScope: "both"`; every spawn is a fresh isolated context — the guarantee the review relies on). The board script lives at `.agents/skills/mismagent-board/scripts/board.py`. The worker-composer's parallel waves map onto the subagent tool's parallel mode (max 8 tasks per call, 4 concurrent — see its skill's pi execution notes); `mismagent-reviewer` is generated glue hosting the `mismagent-code-review` skill in fresh context. pi has no per-agent reasoning knob — to think harder on the adversarial roles (challenger/verifier/architect), pin a stronger `model:` in their `.pi/agents/*.md`.

**Setup (once).** From the mismagent repo: `pi/install.sh <your-project-root>` It copies the skills into `<project>/.agents/skills/`, the prompt templates into `<project>/.pi/prompts/`, the subagent definitions into `<project>/.pi/agents/`, and this file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists — merge it). `[agent]` steps additionally need pi's official `subagent` example extension (pi repo, `packages/coding-agent/examples/extensions/subagent/` — symlink `index.ts` + `agents.ts` into `~/.pi/agent/extensions/subagent/`), always called with `agentScope: "both"`. Verify: `/skill:mismagent-explore` autocompletes. Alternative global install (skills+prompts only): `pi install <path-to-mismagent-repo>/pi`.

A flow to invoke, not a methodology to read: the agents' and skills' instructions are the process.
This file says who owns what and in which order. The core names no project; each project's
**profile** (`<output_dir>/profile.md`, default `.mismagent/profile.md`; template `.agents/skills/mismagent-explore/references/PROFILE.md`,
example `.agents/skills/mismagent-explore/references/profile-example.md`) binds sides, paths, gates and branching.

## Where things live — trunk and features
```
<output_dir>/
  profile.md · context-map.md · architecture.md · code-rules.md · infra-notes.md
  decisions/ · architetture/        # the PROJECT trunk — decided once, amended explicitly
  features/<feature>/               # born and thrown away with the feature
    product-brief.md · tactical-model.md · building-blocks.yaml · UI/ · research/
    blocks/<ctx>/{todo,doing,done}/ · tasks/ · open-questions/ · proofs
```
- **Only the architect writes the trunk**, except `context-map.md`, which the analyst amends (one map,
  never re-forked). Everyone else writes inside `features/<feature>/`.
- A signal is read at the **scope of the artifact it guards**: an empty feature folder says nothing
  about the project. Stack, style, code rules, gate and `run` are deliberated once per project;
  changing one is a superseding ADR the user asked for.

## The three movements
| movement | you | owners (in order) | handoff files |
|---|---|---|---|
| **explore** | in dialogue | `explore` skill (bootstraps the profile if missing) → `mismagent-challenger` → `mismagent-researcher` (if needed) → `mismagent-analyst` | `product-brief.md`, `context-map.md`, the tactical seeds |
| **model** | confirm the boundaries | `/skill:mismagent-model` conducts: `mismagent-tactical-modeler` → `ux-designer` (if UI) → `mismagent-architect` (two passes) → `build-manifest` | `tactical-model.md`, ADRs, `architecture.md`, `code-rules.md`, `building-blocks.yaml`, block files |
| **build** | confirm each release | `/skill:mismagent-worker-composer` → `mismagent-worker` ×N → `mismagent-verifier` (+ `code-review`) | code on the integration line, proofs |

User entry points: the movement commands above, each agent's thin command (`/mismagent-<name>`),
`readiness-gate`, `board`, `run-app-smoke`, `harvest-dev-architecture`. The other skills
(`realize-*`, `write-*`, `code-review`) are invoked by the agents mid-flow.

## Human checkpoints
The challenger's verdict · `NEEDS-INPUT` ambiguities · the architect's stack/style/infra/code-rules
choice · the `tests_nl` elicitation and the R0 cut · a `BOUNCED` block or a spike's evidence · every
release. Nothing else stops for you.

## The rules the flow enforces
1. **Handoff = file.** Every handoff that crosses a movement is a file, never only a message. In a
   read-only harness mode, dispatch only read-only agents and materialize the pending files as the
   first action once writes reopen.
2. **State = folder.** A block's state is its folder (`todo/doing/done`); only the worker-composer
   moves it and merges.
3. **Re-entrance.** Every command re-reads the files and resumes at the first missing artifact; an
   artifact that exists is stated and reopened only on request, never re-deliberated.
4. **Reconciliation.** Two artifacts that disagree in silence are two sources of truth: the writer
   who notices amends the loser in the same pass, or asks.
5. **What crosses a seam is pinned** in the manifest (types, keys, view sources, owners of shared
   artifacts) and the owner's ADRs (delivery guarantees), never invented by parallel workers.
6. **No artifact without a reader**, except a view regenerated from its source (the block files, the
   board).
7. **A gate that cannot go red is not a gate.** It executes the tests it guards; its red-green proof
   is recorded and renewed when its configuration changes.
8. **Release = tag ↔ feature flag.** Never merge or push onto the base branch, and never tag a
   release, without the user's explicit consent.
9. **In doubt, stop and ask.** A slow or hanging step is a strategy to replace (back to the
   architect), never something to wait out.
