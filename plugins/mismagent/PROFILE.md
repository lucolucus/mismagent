# mismAgent — Project profile (TEMPLATE)

> The mismAgent **core** (agents, skills, flow) is **generic and portable**. This file is the
> **binding to your project**: you fill it in per project. Agents and skills never name a
> specific project — they read *"the profile"*.
>
> **Binding (where the active profile lives):** the project's filled-in profile lives in
> **`<output_dir>/profile.md`** — default **`.mismagent/profile.md`** in the project root.
> That is where every agent/skill looks for it; the plugin's `profiles/*.md` are just
> **examples** (see **`profiles/example.md`**, a filled-in fictional instance).
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
```

## Sides (independent deploy units)

One entry for every unit you deploy autonomously. **A single side is legitimate** (desktop app/
monolith): the `projection` of every boundary will be `in-process` and no OpenAPI will exist.

```yaml
sides:
  <side>:                       # e.g. be | fe | sync — or just `app` if single-side
    repo: <path-or-repo-name>   # where this side's code lives
    dev_architecture: <skill>   # the repo's "architecture memory" skill (or: none)
    gate: "<commands>"          # build + test that must turn green
                                # bootstrap: "manual — TBD after the stack ADR" (the architect finalizes it)
    contract: "<mechanism>"     # ONLY for sides with cross-deploy boundaries: how it verifies the
                                # contract / generates the types. Single-side: none
```

## Domain bounded contexts
The natural contexts of the domain (they seed the boundaries and the canonical names):
- `<Context1>`, `<Context2>`, …

## Boundaries & projection
The rule that decides the shape of every inter-context boundary (`mism-build-manifest` applies it):
- `side(consumer) == side(supplier)` → **`in-process`**: port = code interface +
  in-process consumer-driven contract test. No YAML.
- different sides → **`cross-deploy`**: the port is projected into **OpenAPI** + generated types
  + CDC — requires the **`mismagent-cross-deploy`** module (enable it in the marketplace: it is
  the profile that decides the weight of the method).
- **contract format/location** (only if cross-deploy boundaries exist):
  `<e.g. OpenAPI YAML in architetture/api/<feature>.openapi.yaml>`
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
commands", "the side's dev-architecture skill", "the boundary rules", "the branching tool",
"the boundary's projection" → the value comes from HERE. Nothing is hard-coded in the core.
