# mismAgent — Project profile (TEMPLATE)

> The mismAgent **core** (agents, skills, flow) is **generic and portable**. This file is the
> **binding to your project**: you fill it in per project. Agents and skills never name a
> specific project — they read *"the profile"*.
>
> **Binding (where the active profile lives):** the project's filled-in profile lives in
> **`<output_dir>/profile.md`** — default **`.mismagent/profile.md`** in the project root.
> That is where every agent/skill looks for it; the plugin's `profiles/*.md` are just
> **examples** (see **`.agents/skills/mismagent-explore/references/profile-example.md`**, a filled-in fictional instance).
>
> **It is filled in at TWO moments** (a greenfield doesn't know everything yet):
> - **Bootstrap** (prerequisite of *explore*): `output_dir`, language of the ubiquitous
>   language, known bounded contexts, list of sides. These are enough to start.
> - **Post-architect** (inside *model*): `gate`, `dev_architecture`, stack-specifics — they
>   become knowable **only after the stack ADR** (deliberated with the user); it is **the
>   architect** who finalizes them here. Until then: `gate: "manual — TBD after the stack ADR"`.

## Bootstrap (prerequisite of explore)

```yaml
output_dir: .mismagent          # where mismAgent writes its artifacts (recommended default)
ubiquitous_language:
  lang: <it|en|...>             # language of the canonical names = the language the domain speaks
validation_mode: normal         # or: greenfield_from_requirements — the deliverable is (re)built
                                # from the stated requirements ONLY: challenger/analyst never treat
                                # a prior implementation of it as ground truth. It should surface at
                                # bootstrap; if it doesn't, explore ASKS the user explicitly.
materials:                      # what source material EXISTS — declared ONCE, here. `none` is an
                                # answer, not a gap: a skill whose input names sample/ or UI/ reads
                                # THIS field and never hunts for folders that don't exist.
  sample: <path | none>         # domain PDFs/screenshots (analyst, researcher, challenger, ux-designer)
  ui: <path | none>             # pre-existing mockups/UI spikes (ux-designer, architect)
capacity: <team & hours>        # who builds it and with how much time — e.g. "2 devs, ~6h/week" or
                                # "full-agentic". The architect (pass-1) and build-manifest MUST read
                                # it: stack, architecture and waves are sized to the TEAM, never to
                                # the idealized problem. If it doesn't surface, explore ASKS.
```

## Project definition files (the architect writes these in *model* — user-visible)

```yaml
architecture: .mismagent/architecture.md  # the chosen style + module map + allowed dependency
                                          # directions — source for the scaffold's skeleton and
                                          # for the gate's dependency-lint config
code_rules: .mismagent/code-rules.md      # the deliberated code-writing rules, each with its
                                          # enforcement channel (workers apply them; the
                                          # code-review audits the discursive ones)
```

## Sides (independent deploy units)

One entry for every unit you deploy autonomously. **A single side is legitimate** (desktop app/
monolith): the `projection` of every boundary will be `in-process` and no OpenAPI will exist.

```yaml
sides:
  <side>:                       # e.g. be | fe | sync — or just `app` if single-side
    repo: <path-or-repo-name>   # where this side's code lives
    dev_architecture: <skill | path.md>  # the CODEBASE's architecture memory: a harvested SKILL
                                # (harvest-dev-architecture, from real code) or an AUTHORED doc
                                # (the architect writes it BEFORE the first domain wave — its path
                                # here; the worker-composer injects it into every dispatch). It
                                # attaches to the CODEBASE, not the deploy role: sides sharing one
                                # domain codebase point at ONE shared memory — three per-side
                                # copies would describe the same files (friction-log-4 #21/#23/#27).
                                # none = not yet authored/harvested
    gate: "<commands>"          # build + test that must turn green
                                # bootstrap: "manual — TBD after the stack ADR" (the architect finalizes it)
                                # The gate must EXECUTE the tests of the side's whole module graph,
                                # not merely build it (Gradle trap: `:app-X:build` runs app-X's own
                                # check ALONE — dependency modules compile, their tests never run →
                                # every block vacuously green). Discriminating power is proven
                                # red-green once by the wave-0 scaffold; the composer's Phase 1
                                # refuses a gate without the proof (friction-log-4 #17)
    toolchain: "<prerequisite>" # what the gate needs to even START (e.g. "JDK 21 — set JAVA_HOME if
                                # the shell default differs"): the same gate string must not flip
                                # red on a differently-configured shell. Workers and the verifier
                                # run the gate under this. none if the gate is self-sufficient
    ui_render_check: "<mechanism>"  # ONLY for sides that render UI: how a `ui` block proves it
                                # RENDERS (not just that the presenter is green). Either an automated
                                # UI smoke/screenshot test folded INTO the gate, or "manual run-the-app
                                # (recorded)". Read by realize-ui. Sides with no UI: none
    run: "<command + port>"     # ONLY for sides that render UI: how to LAUNCH the side locally —
                                # read by run-app-smoke to produce the recorded render proof
                                # (render-proof/). REQUIRED when ui_render_check is manual (the
                                # worker-composer's readiness bounces without it), and PINNED A
                                # PRIORI: the architect finalizes it (with the gate) BEFORE any
                                # scaffold exists — it is a CONTRACT the wave-0 scaffold must
                                # satisfy (launch task/entry + port), not a wave-3 discovery.
                                # Headless sides: none
    contract: "<mechanism>"     # ONLY for sides with cross-deploy boundaries: how it verifies the
                                # contract / generates the types. Single-side: none
```

## Domain bounded contexts
The natural contexts of the domain (they seed the boundaries and the canonical names):
- `<Context1>`, `<Context2>`, …
- List **only** contexts with a domain language of their own. A cross-cutting architectural concern
  (sync/replication, caching, auth) is an **NFR or an architect spike, not a bounded context** — a
  modeler that takes it literally reifies a zombie context (friction-log-4 #4).

## Boundaries & projection
The rule that decides the shape of every inter-context boundary (`build-manifest` applies it):
- `side(consumer) == side(supplier)` → **`in-process`**: port = code interface +
  in-process consumer-driven contract test. No YAML.
- different sides → **`cross-deploy`**: the port is projected into an executable contract in the
  **form the boundary declares** (`contract_form`) — request/response → **OpenAPI** + generated
  types + CDC; a replication/sync wire (local-first, warm-standby, …) → a **versioned
  event-schema** (e.g. proto + event catalogue, additive evolution) + CDC on the events — requires
  the **`mismagent-cross-deploy`** module (install it with `install.sh --with-cross-deploy`: it is
  the profile that decides the weight of the method).
- **contract form/location per boundary** (only if cross-deploy boundaries exist):
  `<e.g. openapi in architetture/api/<feature>.openapi.yaml · event-schema in contracts/proto/>`
- **authorship:** reads consumer-driven; writes producer-driven; the architect arbitrates.

## Branching
- **tool:** `<script/command, or "manual">`
- **commit:** `"<message format>"`
- **model:** `<branch per block/story; merge strategy; what commits directly>`

## Boundary rules
What an agent must NEVER do, and who commits where. Pick the form:
- **Multi-repo / multi-side:** `<never one side's code in another side's repo>`;
  `<every sub-repo has its own .git: commit there, not in the parent>`.
- **Single repo / single-side:** `<the boundary is the MODULE/package: never write outside
  your own block's package; the other context is touched only via the port>`.
- Always: `<never commit secrets / .env / certificates / DB files and backups>`.

---
*How the agents use it:* wherever an instruction says "the side's repo", "the side's gate
commands", "the codebase's dev-architecture memory", "the boundary rules", "the branching tool",
"the boundary's projection" → the value comes from HERE. Nothing is hard-coded in the core.
