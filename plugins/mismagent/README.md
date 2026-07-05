# mismAgent plugin (kernel)

Packages the **mismAgent** flow as a Claude Code plugin: skills, agents, commands and the map in
a single, installable folder. It is not a methodology to read: it is a flow to invoke.

**Kernel + modules by necessity.** This plugin is the **kernel**: it is enough on its own for a
single-side project. The weight scales with the case — modules are enabled only when the project
requires them:
- **`mismagent-cross-deploy`** (same marketplace) — when a boundary crosses a deploy boundary:
  `seam-cross-deploy` + `create-contract` (the port → OpenAPI + generated types + CDC).
- The superseded pieces of the file-driven flow live in **`attic/`** at the repo root, outside the
  registry (see `attic/README.md`): no agent can invoke them by mistake.

**Core + profile.** The core (skills, agents, commands, flow) is **portable** and names no
project. Each project provides its own profile — **the active profile lives in
`<output_dir>/profile.md`, default `.mismagent/profile.md`** (template: `PROFILE.md`; filled-in
example: `profiles/example.md`): from there agents read sides, repos, gates, dev-architecture
skills, boundary rules, boundary projections and the commit format.

## Contents (kernel)
- `methodology/mismagent.md` — the map of the flow (what to invoke, in what order).
  `redesign/composer-spec.md` — rationale of the architecture-driven build.
- `skills/`:
  - `explore` (explore) — orchestrates the dialogue; profile bootstrap; challenger + analyst.
  - `build-manifest` (model) — from the tactical model → **building-block manifest**
    (types pinned at the boundaries, projection, `tests_nl`).
  - `readiness-gate` (model→build) — survival test on the manifest.
  - `realize-{aggregate,application-service,port,adapter,read-model,ui,scaffold}` + `seam-in-process`
    (build) — the worker's skills: block-type × boundary projection (`scaffold` = the greenfield
    wave-0 buildable skeleton).
  - `ux-designer` (model) — imagines the UI → views (if the feature has a UI).
  - `code-review` (build) — adversarial semantic review with fresh context.
  - writers: `write-context-map`, `write-infra-notes`, `write-adr`, `write-task`.
- `agents/`:
  - explore — `mismagent-challenger` (fresh-context adversary), `mismagent-researcher`, `mismagent-analyst`.
  - model — `mismagent-tactical-modeler` (DDD tactical), `mismagent-architect` (architecture + ADRs,
    guarantor of the boundaries; foundational decisions — stack + architecture style + infra —
    deliberated with the user via a two-pass headless pattern).
  - build — `mismagent-worker` (realizes ONE building block), `mismagent-verifier` (read-only, fresh context).
- `commands/` — **`worker-composer`** (architecture-driven build: sole git-writer, merge =
  composition, D2 on the boundary) · **`board`** (read-only live view of the blocks + their state) ·
  **a thin command per agent** (`challenger`, `researcher`, `analyst`, `tactical-modeler`, `architect`,
  `verifier`, `worker`) so each agent is invocable as `/mismagent:<name>` (it dispatches the
  `mismagent-<name>` subagent).
- `tools/` — `board.py`: the zero-dep read-only board server (launched by `/mismagent:board`).

## The flow
**explore** (`/mismagent:explore` → `mismagent-challenger` → `mismagent-analyst`) →
**model** (`mismagent-tactical-modeler` → `ux-designer` → `mismagent-architect` → `build-manifest`
→ if a boundary is cross-deploy: `create-contract`, from the module) →
**build** (`/mismagent:worker-composer` → `mismagent-worker` ×N with block-type × projection skills →
`mismagent-verifier` + `code-review` → confirmation → feature-flag).

## Installation (local marketplace)
The **marketplace is the root of this repo** (it contains `.claude-plugin/marketplace.json`,
which lists kernel and modules). On a clean project the plugin **is not active by itself**: it
must be registered with the **ABSOLUTE path** (a relative path is interpreted as a GitHub repo):

**A. Interactive**
```
/plugin marketplace add /absolute/path/to/the/mismagent/repo
/plugin install mismagent@mismagent-method
/plugin install mismagent-cross-deploy@mismagent-method   # ONLY if the profile has cross-deploy boundaries
/reload-plugins
```

**B. Direct in `~/.claude/settings.json`**
```json
"extraKnownMarketplaces": { "mismagent-method": { "source": { "source": "directory", "path": "/absolute/path/to/the/mismagent/repo" } } },
"enabledPlugins": { "mismagent@mismagent-method": true }
```
then `/reload-plugins`.

After installation **everything you invoke is namespaced under `/mismagent:`**: skills and commands
(`/mismagent:explore`, `/mismagent:worker-composer`, … and from the module
`/mismagent-cross-deploy:create-contract`), **and each agent** via its thin command
(`/mismagent:architect` → dispatches the `mismagent-architect` subagent). The agents also still show up
in `/agents` under their bare `mismagent-*` name and can be dispatched directly. Verify:
`/mismagent:explore` must appear among the available skills.

## Note
The flow hard-codes no project specifics: the side repos' paths, the build/test commands (gate),
the boundary projections and the dev-architecture skills come from the active profile
(`.mismagent/profile.md`). To reuse it elsewhere, just write a new profile — and enable the
modules that the project actually requires.
