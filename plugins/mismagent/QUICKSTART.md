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

Verify: the skill **`/mismagent:mism-explore`** (namespace included!) must appear among the
available ones. **Agents** (`mism-challenger`, `mism-analyst`, …) are not slash-commands: they
show up in `/agents` and the assistant dispatches them. *(After installing/changing, a
`/reload-plugins` may be needed for the new ones to enter the registry.)*

## 2. Profile: the BOOTSTRAP is enough to start
You don't need the full profile before explore — you need the **bootstrap** (`mism-explore`
also creates it at step 0 if it's missing): in `.mismagent/profile.md` put
- **output_dir** (recommended default: `.mismagent`),
- **ubiquitous_language.lang** (the language the domain speaks),
- the known **bounded contexts** and the **list of sides** (a single one is perfectly fine).

The rest is completed **inside model**: `gate` and `dev_architecture` only become knowable
after the **stack ADR** (which the architect **deliberates with you**, never alone) — until then
`gate: "manual — TBD after the stack ADR"`. Template: `PROFILE.md`; filled-in example: `profiles/example.md`.

## 3. Launch the flow
`/mismagent:mism-explore` on the idea → `mism-challenger` (demolishes) → `mism-researcher`/
`mism-analyst` (model) → **model** (ask to dispatch `mism-tactical-modeler`, then
`mism-architect`; skill `/mismagent:mism-ux-designer` if there is UI, `/mismagent:mism-build-manifest`
for the manifest; `/mismagent-cross-deploy:mism-create-contract` — from the module — only if a
boundary is cross-deploy) →
**build** (`/mismagent:composer <feature>` → `mism-worker` ×N → verifier + code-review →
you confirm → flag).

---

## Greenfield traps (read BEFORE starting)
- **`dev_architecture: none` at the start.** On a new project you don't have golden
  files/conventions yet: put `none`. When the patterns stabilize, write a
  `<side>-dev-architecture` skill (modeled on a real per-side golden-files doc) and point the
  profile at it.
- **The stack is decided in model, WITH you.** Don't fill in `gate`/stack in the profile by
  guessing: the architect presents the alternatives, you choose, the stack ADR gets written
  afterwards — and the architect finalizes the `gate` in the profile.
- **Boundaries pinned before the workers.** The Composer's readiness blocks a manifest with
  unpinned boundary types (Published Language): it is the most expensive lesson of the first run —
  two workers blind on an under-specified boundary produce pieces that do NOT compose.
- **Single-side is not a degraded case.** A single side ⇒ all boundaries `in-process`
  (port = interface + contract test): no OpenAPI, and the `mismagent-cross-deploy` module
  **simply doesn't get enabled** — the kernel is enough, and that's fine.

## When something doesn't add up
The first real run surfaces the holes in the core. Keep a **`MISMAGENT-LOG.md`** in the project
root and record **every friction point the moment it happens** (which skill/agent, what it was
attempting, what jammed, `core` vs `profile`, proposed fix) — it is the mechanism by which the
methodology matures: the reviews and the core fixes are born from the log.
