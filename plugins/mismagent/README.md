# mismAgent plugin (kernel)

Packages the **mismAgent** flow as a Claude Code plugin: skills, agents, commands and the map in
a single, installable folder. It is not a methodology to read: it is a flow to invoke.

**Kernel + modules by necessity.** This plugin is the **kernel**: it is enough on its own for a
single-side project. The weight scales with the case — modules are enabled only when the project
requires them:
- **`mismagent-cross-deploy`** (same marketplace) — when a boundary crosses a deploy boundary:
  `seam-cross-deploy` + `mism-create-contract` (the port → OpenAPI + generated types + CDC).
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
  - `mism-explore` (explore) — orchestrates the dialogue; profile bootstrap; challenger + analyst.
  - `mism-build-manifest` (model) — from the tactical model → **building-block manifest**
    (types pinned at the boundaries, projection, `tests_nl`).
  - `mism-readiness-gate` (model→build) — survival test on the manifest.
  - `realize-{aggregate,application-service,port,adapter,read-model}` + `seam-in-process`
    (build) — the worker's skills: block-type × boundary projection.
  - `mism-ux-designer` (model) — imagines the UI → views (if the feature has a UI).
  - `mism-code-review` (build) — adversarial semantic review with fresh context.
  - writers: `mism-write-context-map`, `mism-write-infra-notes`, `mism-write-adr`, `mism-write-task`.
- `agents/`:
  - explore — `mism-challenger` (fresh-context adversary), `mism-researcher`, `mism-analyst`.
  - model — `mism-tactical-modeler` (DDD tactical), `mism-architect` (architecture + ADRs,
    guarantor of the boundaries; stack decisions are deliberated with the user).
  - build — `mism-worker` (realizes ONE building block), `mism-verifier` (read-only, fresh context).
- `commands/` — **`composer`** (architecture-driven build: sole git-writer, merge =
  composition, D2 on the boundary).

## The flow
**explore** (`/mismagent:mism-explore` → `mism-challenger` → `mism-analyst`) →
**model** (`mism-tactical-modeler` → `mism-ux-designer` → `mism-architect` → `mism-build-manifest`
→ if a boundary is cross-deploy: `mism-create-contract`, from the module) →
**build** (`/mismagent:composer` → `mism-worker` ×N with block-type × projection skills →
`mism-verifier` + `mism-code-review` → confirmation → feature-flag).

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

After installation **skills and commands are namespaced with the plugin name**: invoke them as
`/mismagent:mism-explore`, `/mismagent:composer`, … (and from the module:
`/mismagent-cross-deploy:mism-create-contract`). **Agents**, on the other hand, show up in
`/agents` under their bare `mism-*` name and are dispatched by the assistant (they are not
slash-commands). Verify: `/mismagent:mism-explore` must appear among the available skills.

## Note
The flow hard-codes no project specifics: the side repos' paths, the build/test commands (gate),
the boundary projections and the dev-architecture skills come from the active profile
(`.mismagent/profile.md`). To reuse it elsewhere, just write a new profile — and enable the
modules that the project actually requires.
