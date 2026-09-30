# Profile: example — "machinecare" (fictional, multi-side, one repo)

> **Filled-in example** of `../PROFILE.md`: a fictional machine-maintenance SaaS with BE and FE
> sides. On your project, write an analogous one in `<output_dir>/profile.md`.

## Bootstrap (prerequisite of explore)

```yaml
output_dir: .mismagent
ubiquitous_language:
  lang: en          # the language the domain speaks — keep the domain's own terms, never translate them
validation_mode: normal   # a rebuild-from-requirements validation run would say greenfield_from_requirements
materials:
  sample: sample/   # supplier PDFs + maintenance-sheet screenshots live here
  ui: none          # no pre-existing mockups — the ux-designer starts from the brief
capacity: "2 devs, ~10h/week total"   # architect + build-manifest size stack and waves on this
```

## Project definition files (the architect wrote these in *model*)

```yaml
architecture: .mismagent/architecture.md   # chosen style + module map + allowed dependency directions
code_rules: .mismagent/code-rules.md       # the deliberated rules, each with its enforcement channel
```

## Sides

```yaml
sides:
  be:
    path: be                                # e.g. .NET, Clean Arch + DDD, PostgreSQL
    dev_architecture: be-dev-architecture   # golden files in be/docs/dev-architecture/
    gate: "dotnet build && dotnet test && dotnet test --filter Contract"
    gate_files: ["be/**/*.csproj", "be/*.sln", "be/global.json"]
    gate_verify: "dotnet build --no-incremental && dotnet test && dotnet test --filter Contract"
    gate_after_release: "dotnet test --filter MigrationFromReleased"   # on at the first release
    toolchain: ".NET SDK 8 (pinned by global.json)"
  fe:
    path: fe                                # e.g. Next.js + TypeScript
    dev_architecture: fe-dev-architecture   # golden files in fe/docs/dev-architecture/
    gate: "npm run lint && npm run build && npm run test && npm run test:contract && npm run test:ui"
    gate_files: ["fe/package.json", "fe/package-lock.json", "fe/*.config.*"]
    gate_after_release: none
    toolchain: "Node 20 (pinned by .nvmrc)"
    ui_render_check: "Playwright smoke + screenshot on the key screens (npm run test:ui in the gate)"
    run: "npm run dev (http://localhost:3000)"
  infra:
    path: infra
    dev_architecture: none
    gate: "—"
```

## Boundaries
- The FE reaches the boundaries of a BE context over HTTP: a project choice (OpenAPI + generated
  types, per an ADR), checked by `npm run test:contract` in the gate — not a harness concept.
- **authorship:** reads **consumer-driven** (the views are defined by the FE), writes
  **producer-driven** (the commands by the BE/domain); the architect arbitrates feasibility/coherence.

## Branching
- **base:** `main` (checked: it exists)
- **integration:** `integration/<feature>` (the default), cut from `main`
- **tool:** `manual`
- **commit:** `"<SIDE>: <block-id> — <description>"` — SIDE ∈ {BE, FE}
- **model:** branch per **block** `block/<id>`, merged by the worker-composer into the integration
  line; `.mismagent/` travels on that line with the code; the integration line reaches `main` only
  when the user asks.

## Boundary rules
- Never **FE** code under `be/` or vice versa.
- Never commit `cert/`, `.env`, `appsettings.*`, secrets, local DB files or backups.
