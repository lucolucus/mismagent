# mismAgent — Codex packaging

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

> **Codex mapping (this packaging).** `[skill]`/`[command]` steps are Codex **skills** — invoke with `$mismagent-<name>` (or `/skills`). `[agent]` steps are Codex **subagents** in `.codex/agents/` — ask Codex to *"spawn `mismagent-<name>` on <input>"* (Codex spawns them only on explicit request). Skill names carry the `mismagent-` prefix because Codex has no namespaces. The board script lives at `@@MISMAGENT_SKILLS@@/mismagent-board/scripts/board.py`. Subagents ship with a tuned `model_reasoning_effort` (challenger/verifier/architect: high) and a `sandbox_mode` matching their role (challenger, verifier: read-only). The worker-composer's parallel waves map onto `spawn_agents_on_csv` (see its skill's Codex execution notes); the `[agents]` config (`max_threads`, default 6) is the concurrency cap.

> **Recording duty (the caller's).** Whoever spawns a subagent is the **recorder**: the challenger's debate and the user's `KILL`/`RESHAPE`/`PROCEED` choice, the user's answer to the architect's `STACK_PROPOSAL`/`ARCH_PROPOSAL`/`INFRA_QUESTIONS` or to the tactical-modeler's `NEEDS-INPUT`, a worker's `DECISIONS`, a reviewer's objection to a `D-NNNN` (into its `Debate`) — each non-obvious choice as an entry of `features/<feature>/decisions.md` (format: `@@MISMAGENT_SKILLS@@/mismagent-worker-composer/references/CLI.md`; validate with its `why check`). Subagents never write that file: they cite `D-NNNN` in their notes.

**Setup (once).** From the mismagent repo: `codex/install.sh <your-project-root>` It copies the skills into `<project>/.agents/skills/`, the subagents into `<project>/.codex/agents/`, and this file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists — merge it), and anchors every tool path to the absolute installed skills directory (re-run it after moving the project). Verify: `/skills` lists `mismagent-explore`.

A flow to invoke, not a methodology to read: the agents' and skills' instructions are the process.
This file says who owns what and in which order. The core names no project; each project's
**profile** (`<output_dir>/profile.md`, default `.mismagent/profile.md`; template `@@MISMAGENT_SKILLS@@/mismagent-explore/references/PROFILE.md`,
example `@@MISMAGENT_SKILLS@@/mismagent-explore/references/profile-example.md`) binds sides, paths, gates and branching.

## Where things live — trunk and features
```
<output_dir>/
  profile.md · context-map.md · architecture.md · code-rules.md · infra-notes.md
  decisions/ · architetture/        # the PROJECT trunk — decided once, amended explicitly
  features/<feature>/               # born with the feature; archived, never deleted
    product-brief.md · tactical-model.md · building-blocks.yaml · decisions.md · UI/ · research/
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
| **explore** | in dialogue | `explore` skill → `mismagent-challenger` → `mismagent-researcher` (if needed) → `mismagent-analyst` | `product-brief.md`, `context-map.md`, the tactical seeds |
| **model** | confirm the boundaries | `$mismagent-model` conducts: `mismagent-tactical-modeler` → `ux-designer` (if UI) → `mismagent-architect` (two passes) → `build-manifest` | `tactical-model.md`, ADRs, `architecture.md`, `code-rules.md`, `building-blocks.yaml`, block files |
| **build** | confirm each release | `$mismagent-worker-composer` → `mismagent-worker` ×N → `mismagent-verifier` (+ `code-review`) | code on the integration line, proofs |

User entry points: the movement commands above, each agent as a subagent (*"spawn `mismagent-<name>`"*),
`readiness-gate`, `board`, `run-app-smoke`, `harvest-dev-architecture`. The other skills
(`realize-*`, `write-*`, `code-review`) are invoked by the agents mid-flow.

## Human checkpoints
The challenger's verdict · `NEEDS-INPUT` ambiguities · the architect's stack/style/infra/code-rules
choice · the `tests_nl` elicitation and the R0 cut · a `BOUNCED` block or a spike's evidence · every
release. Nothing else stops for you.

## The rules the flow enforces
1. **Handoff = file.** Every handoff that crosses a movement is a file, never only a message. A non-obvious choice, its debate and who decided it →
   `features/<feature>/decisions.md` (format: `@@MISMAGENT_SKILLS@@/mismagent-worker-composer/references/CLI.md`); a subagent that may not write it
   returns `DECISIONS`, which its conductor appends.
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
