# mismAgent — Quickstart (project from scratch)

mismAgent is **generic core + profile**: the method is portable, each project provides its own
profile in **`.mismagent/profile.md`**. Three steps to start on a clean project.

## 1. Activate the plugin (it is not active by itself)
Claude Code must "see" the plugin's skills/agents/commands. Register the **local marketplace**
(= the **root of the mismagent repo**) with the **ABSOLUTE path** (a relative path is interpreted
as a GitHub repo):
```
/plugin marketplace add /absolute/path/to/the/mismagent/repo
/plugin install mismagent@mismagent-method
/plugin install mismagent-cross-deploy@mismagent-method   # ONLY if you have cross-deploy boundaries
/reload-plugins
```
(direct equivalent: `extraKnownMarketplaces` with `source: directory` + `enabledPlugins` in
`~/.claude/settings.json`, then `/reload-plugins` — see README §Installation).

Verify: the skill **`/mismagent:explore`** (namespace included!) must appear among the
available ones. **Everything is invocable under `/mismagent:`** — skills, the `worker-composer`
command, and each **agent** via its thin command (`/mismagent:architect`, `/mismagent:analyst`, … →
they dispatch the `mismagent-<name>` subagent; the agents also still show up in `/agents`). *(After
installing/changing, a `/reload-plugins` may be needed for the new ones to enter the registry.)*

## 2. Profile: the BOOTSTRAP is enough to start
The profile is the **project's junction point**: you write it **once**, on the first feature, and
every later feature reads it (features are folders under `.mismagent/features/<feature>/` — they
never rewrite the profile or re-deliberate the stack). You don't need the full profile before
explore — you need the **bootstrap** (`explore` also creates it at step 0 if it's missing): in
`.mismagent/profile.md` put
- **output_dir** (recommended default: `.mismagent`),
- **ubiquitous_language.lang** (the language the domain speaks),
- the known **bounded contexts** and the **list of sides** (a single one is perfectly fine),
- **materials** (what source material exists — `sample:`/`ui:` path or `none`: declared once, so
  no skill hunts for folders that don't exist) and **capacity** (who builds, with how many hours —
  the architecture is sized to the team).

The rest is completed **inside model**: `gate` and `dev_architecture` only become knowable
after the **stack ADR** (which the architect **deliberates with you**, never alone) — until then
`gate: "manual — TBD after the stack ADR"`. Template: `PROFILE.md`; filled-in example: `profiles/example.md`.

## 3. Launch the flow
`/mismagent:explore` on the idea → `/mismagent:challenger` (demolishes) → `/mismagent:researcher` /
`/mismagent:analyst` (model) → **model** (**`/mismagent:model <feature>`** — the conductor: it runs
tactical-modeler → ux-designer if there is UI → architect → build-manifest →
`create-contract` if a boundary is cross-deploy, stopping only where YOU decide; the single
commands stay invocable step-by-step) →
**build** (`/mismagent:worker-composer <feature>` → `mismagent-worker` ×N → verifier + code-review →
you confirm → flag).

---

## Greenfield traps (read BEFORE starting)
- **`dev_architecture: none` at the start — then TWO routes fill it.** On a new project you don't
  have golden files/conventions yet: put `none`. Before the **first domain wave** the architect
  **AUTHORS** the codebase's style memory (aggregate shape, test conventions — deliberated with
  you; the worker-composer injects it into every worker dispatch — without it, N parallel workers
  invent N divergent conventions). After the first green slice,
  **`/mismagent:harvest-dev-architecture`** harvests the real conventions from the done blocks'
  code and **grounds/reconciles** that memory (one per CODEBASE — sides sharing the code share
  it), pointing the profile at it.
- **The stack is decided in model, WITH you.** Don't fill in `gate`/stack in the profile by
  guessing: the architect presents the alternatives, you choose, the stack ADR gets written
  afterwards — and the architect finalizes the `gate` in the profile (and, for UI sides, the
  `run` binding: pinned **before** the scaffold, which must then satisfy it).
- **Boundaries pinned before the workers.** The worker-composer's readiness blocks a manifest with
  unpinned boundary types (Published Language): it is the most expensive lesson of the first run —
  two workers blind on an under-specified boundary produce pieces that do NOT compose.
- **Single-side is not a degraded case.** A single side ⇒ all boundaries `in-process`
  (port = interface + contract test): no OpenAPI, and the `mismagent-cross-deploy` module
  **simply doesn't get enabled** — the kernel is enough, and that's fine.
- **Someone has to scaffold the buildable skeleton.** In greenfield there is no Gradle/npm/csproj
  project yet, so the `gate` can't even run. `build-manifest` emits a **wave-0 `scaffold` block**; the
  worker-composer builds it **first** (via `realize-scaffold`) and only then the owner blocks have
  something to compile against. Don't expect the architect to scaffold — it writes design, not code.
- **The repo must be under git.** The worker-composer lives on worktrees + merges. If you start in a
  non-git folder, its Phase 1 will ask you to confirm a `git init` + first commit before proceeding.
- **"Where are the tasks?"** Run **`/mismagent:board`** — a read-only live view of the blocks and
  their state. The work-item *is* the block: `build-manifest` seeds one **rich `<id>.md` file per
  block** in `.mismagent/features/<feature>/blocks/<context>/{todo,doing,done}/` (spec + `## What to do`/
  `## Tasks`/`## Dependencies`, **status-less, no checkboxes**) — its **folder is its status**, moved only
  by the worker-composer. The board renders those files + their folder position; it never writes them.
  The block files are a derived projection of the authoritative `building-blocks.yaml` (re-run
  `build-manifest` to refresh). The legacy file-driven flow lives in `attic/`.

## When something doesn't add up
The first real run surfaces the holes in the core. Keep a **`MISMAGENT-LOG.md`** in the project
root and record **every friction point the moment it happens** (which skill/agent, what it was
attempting, what jammed, `core` vs `profile`, proposed fix) — it is the mechanism by which the
methodology matures: the reviews and the core fixes are born from the log.
