# mismAgent — Project profile (TEMPLATE)

> The core (agents, skills, flow) is generic; this file is the **binding to your project**. Agents
> read *"the profile"* and never name a project. The active profile lives in
> **`<output_dir>/profile.md`** (default `.mismagent/profile.md`); `profiles/example.md` is a
> filled-in fictional instance.
>
> **One profile per project** — the junction point, not a per-feature artifact. Features
> (`<output_dir>/features/<feature>/`) read it and never rewrite it; `gate`, `run`, `architecture`
> and `code_rules` change only when the user asks, through a superseding ADR.
>
> **Filled in at two moments, both on the first feature:**
> - **Bootstrap** (explore creates it if missing): output dir, language, validation mode, materials,
>   capacity, contexts, sides.
> - **Post-architect** (model): `gate` and its companions, `run`, `dev_architecture`, the definition
>   files — knowable only after the stack ADR. Until then: `gate: "manual — TBD after the stack ADR"`.

## Bootstrap

```yaml
output_dir: .mismagent          # where mismAgent writes its artifacts
ubiquitous_language:
  lang: <it|en|...>             # the language the domain speaks — canonical names are never translated
validation_mode: normal         # or greenfield_from_requirements: the deliverable is (re)built from the
                                # stated requirements ONLY — no prior implementation is ground truth.
                                # explore asks if it does not surface.
materials:                      # what source material EXISTS; `none` is an answer — no skill hunts
  sample: <path | none>         # domain PDFs/screenshots (analyst, researcher, challenger, ux-designer)
  ui: <path | none>             # pre-existing mockups (ux-designer, architect)
capacity: <team & hours>        # e.g. "2 devs, ~6h/week" or "full-agentic" — the architect and
                                # build-manifest size stack, architecture and waves on it.
                                # explore asks if it does not surface.
```

## Project definition files (written by the architect)

```yaml
architecture: .mismagent/architecture.md  # style + module map + allowed dependency directions
                                          # (source of the scaffold and of the dependency lint)
code_rules: .mismagent/code-rules.md      # the deliberated rules, each with its enforcement channel
```

## Sides (independent deploy units)

A single side is legitimate: every boundary is then `in-process` and no contract file exists.

```yaml
sides:
  <side>:                       # e.g. be | fe | sync — or `app` if single-side
    path: <dir>                 # the side's code, relative to the project root (one repo per project)
    dev_architecture: <skill | path.md | none>   # the CODEBASE's style memory: authored by the
                                # architect before the first domain wave, or harvested from real code.
                                # Sides sharing one codebase point at ONE memory. The worker-composer
                                # injects it into every dispatch.
    gate: "<commands>"          # build + test that must turn green; bootstrap value
                                # "manual — TBD after the stack ADR". It must EXECUTE the tests of the
                                # side's whole module graph, not merely build it. Its discriminating
                                # power is proven red-green (at the scaffold on greenfield); the
                                # worker-composer refuses a gate without a fresh proof.
    gate_files: [<glob>…]       # REQUIRED whenever `gate` is set: the files defining the side's
                                # build, modules, tests and registered checks (repo-relative, `**`
                                # allowed). They key the gate proof: a change to them makes it stale.
    gate_verify: "<commands>"   # optional: `gate` + the stack's re-run switch (no cached test phase); verifier and candidate run it
    gate_after_release: "<steps>" # checks that protect RELEASED versions (e.g. against a released
                                # schema). Kept out of `gate` until the side's first release, when
                                # the worker-composer appends them and records `switched@<tag>`.
                                # none if every step matters from day one.
    toolchain: "<prerequisite>" # what the gate needs to START (e.g. a pinned runtime/SDK and how to
                                # select it), so the same gate never flips on another shell. none if
                                # self-sufficient.
    ui_render_check: "<mechanism>"  # UI sides only: how a `ui` block proves it RENDERS — an automated
                                # smoke/screenshot test folded into the gate, or
                                # "manual run-the-app (recorded)". none otherwise.
    run: "<command + port>"     # UI sides only: how to launch the side locally (run-app-smoke).
                                # REQUIRED when ui_render_check is manual. Pinned by the architect
                                # BEFORE any scaffold: a contract the wave-0 scaffold satisfies.
    contract: "<mechanism>"     # sides with cross-deploy boundaries only: how the side verifies the
                                # contract / generates its types. none otherwise.
```

Keep every gate step cheap by strategy (standard migrations, faithful in-memory substrates,
incremental per-module builds): a slow or hanging step is replaced by the architect, never waited out.

## Build loop (optional — defaults shown; read by the worker-composer)

```yaml
build:
  max_parallel_workers: 4       # the wave's cap — size it to `capacity` and to the machine (N workers
                                # = N gates at once)
  model_routing:                # the model follows the ACTION
    tiers: { light: haiku, standard: sonnet, deep: opus }   # rebind to your harness' models
    by_action: {}               # override a row, e.g. { adapter: deep, code-review: standard } —
                                # keys: run-app-smoke, verifier, code-review, or a block type
  review_depth_by_type:         # how hard D1 looks
    ui: standard                # standard = one verifier on the standard tier
    adapter: standard
    read-model: standard
    aggregate: deep             # deep = verifier + separate code-review, both deep
    port: deep
    application-service: deep   # a cross-deploy seam, model_hint: deep or a rework → deep
```

## Domain bounded contexts
- `<Context1>`, `<Context2>`, … — only contexts with a domain language of their own. A cross-cutting
  concern (sync, caching, auth) is an NFR or a spike, not a bounded context.

## Boundaries & projection (build-manifest applies it)
- `side(consumer) == side(supplier)` → **`in-process`**: a code interface + an in-process
  consumer-driven contract test.
- different sides → **`cross-deploy`**, in the `contract_form` the boundary declares:
  request/response → **OpenAPI** + generated types + CDC; replication/sync → a **versioned
  event-schema** with additive evolution + CDC on the events. Requires the `mismagent-cross-deploy`
  module.
- **contract location** (cross-deploy only): `<e.g. architetture/api/<introducing-feature>.openapi.yaml ·
  contracts/<schema dir>/>` — one OpenAPI file per boundary for the project's life, named after the
  feature that introduced it; later features extend it (`contract_path`).
- **authorship:** reads consumer-driven, writes producer-driven; the architect arbitrates.

## Branching
- **tool:** `<script/command, or "manual">`
- **commit:** `"<message format>"`
- **model:** `<branch per block; merge strategy; what commits directly — never <output_dir>/: it
  travels on the integration line>`

## Boundary rules
What an agent must NEVER do:
- `<write outside its side's path or its own block's module; another side or context is touched only
  via its port or contract>`
- `<commit secrets / .env / certificates / DB files and backups>`

---
Wherever an instruction says "the side's path", "the gate", "the dev-architecture memory", "the
boundary rules", "the branching tool" or "the boundary's projection", the value comes from HERE.
