# mismAgent plugin (kernel)

Packages the **mismAgent** flow as a Claude Code plugin: skills, agents, commands and the map in
a single, installable folder. It is not a methodology to read: it is a flow to invoke.

**One plugin.** It knows one kind of boundary (a consumer-owned port + its contract test); how a
boundary travels over a network is the project's decision (its ADRs, code rules and gate).
The superseded pieces of the file-driven flow live in **`attic/`** at the repo root, outside the
  registry (see `attic/README.md`): no agent can invoke them by mistake.

**Core + profile.** The core (skills, agents, commands, flow) is **portable** and names no
project. Each project provides its own profile — **the active profile lives in
`<output_dir>/profile.md`, default `.mismagent/profile.md`**, and it is the project's **junction
point**: written once, read by every feature. Features are folders under
`<output_dir>/features/<feature>/`; the project trunk (`context-map.md`, `architecture.md`,
`code-rules.md`, `infra-notes.md`, `decisions/`, `architetture/`) sits in the `<output_dir>` root and
only the architect writes it, except `context-map.md`, which the **analyst** amends. Template:
`PROFILE.md`; filled-in example: `profiles/example.md`.

## Contents (kernel)
- `methodology/mismagent.md` — the map of the flow (who owns what, in what order).
- `skills/`:
  - `explore` (explore) — orchestrates the dialogue; profile bootstrap; challenger + analyst.
  - `build-manifest` (model) — from the tactical model → **building-block manifest**
    (types pinned at the boundaries, `tests_nl`).
  - `readiness-gate` (model→build) — optional pre-flight of the worker-composer's readiness (`MM lint`).
  - `realize-{aggregate,application-service,port,adapter,read-model,ui,scaffold}` (build) — the
    worker's skills, one per block type (`scaffold` = the greenfield wave-0 buildable skeleton).
  - `ux-designer` (model) — imagines the UI → views (if the feature has a UI).
  - `code-review` (build) — adversarial semantic review with fresh context.
  - writers: `write-context-map` (the PROJECT strategic map), `write-tactical-model` (the feature's
    tactical level), `write-infra-notes`, `write-adr`, `write-task`.
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
- `tools/` — `board.py` (the read-only board server of `/mismagent:board`) · `mismagent.py` (the
  build's deterministic tool: lint, ready set, state moves, ledger, candidate merge — `tools/CLI.md`).
- `hooks/` — a guard denying git merges/pushes/rebases/state moves to workers and verifier (partial).

## The flow
**explore** (`/mismagent:explore` → `mismagent-challenger` → `mismagent-analyst`) →
**model** (`mismagent-tactical-modeler` → `ux-designer` → `mismagent-architect` → `build-manifest`
) →
**build** (`/mismagent:worker-composer` → `mismagent-worker` ×N with block-type skills →
`mismagent-verifier` (+ `code-review` on deep-review blocks) → confirmation per release → feature-flag).

## Installation (local marketplace)
The **marketplace is the root of this repo** (`.claude-plugin/marketplace.json`). Register it with the **ABSOLUTE path** (a relative path is read as a GitHub repo):

**A. Interactive**
```
/plugin marketplace add /absolute/path/to/the/mismagent/repo
/plugin install mismagent@mismagent-method
/reload-plugins
```

**B. Direct in `~/.claude/settings.json`**
```json
"extraKnownMarketplaces": { "mismagent-method": { "source": { "source": "directory", "path": "/absolute/path/to/the/mismagent/repo" } } },
"enabledPlugins": { "mismagent@mismagent-method": true }
```
then `/reload-plugins`.

After installation **everything you invoke is namespaced under `/mismagent:`**: skills and commands
(`/mismagent:explore`, `/mismagent:worker-composer`, …), **and each agent** via its thin command
(`/mismagent:architect` → the `mismagent-architect` subagent; also in `/agents` by bare name). Verify:
`/mismagent:explore` must appear among the available skills.

## Note
The flow hard-codes no project specifics: the sides' paths, the build/test commands (gate),
and the dev-architecture memories come from the active profile (`.mismagent/profile.md`). To reuse
it elsewhere, just write a new profile.
