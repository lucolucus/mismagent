# Profile: example — "machinecare" (fictional multi-side meta-repo)

> **Filled-in example** of `../PROFILE.md`, for a fictional machine-maintenance SaaS with
> independent BE/FE deploy units. Use it as a model of what a complete profile looks like;
> on your project, write an analogous one in `<output_dir>/profile.md` (default
> `.mismagent/profile.md`). For a single-side project, see the single-side notes in the template.

## Bootstrap (prerequisite of explore)

```yaml
output_dir: .mismagent
ubiquitous_language:
  lang: en          # the language the domain speaks — keep the domain's own terms, never translate them
```

## Sides (independent deploy units)

```yaml
sides:
  be:
    repo: machinecare-be                    # e.g. .NET, Clean Arch + DDD, PostgreSQL
    dev_architecture: be-dev-architecture   # golden files in machinecare-be/docs/dev-architecture/
    gate: "dotnet build && dotnet test && dotnet test --filter Contract"
    contract: "swagger.json compared against the YAML + response-shape tests on the real body"
  fe:
    repo: machinecare-fe                    # e.g. Next.js + TypeScript
    dev_architecture: fe-dev-architecture   # golden files in machinecare-fe/docs/dev-architecture/
    gate: "npm run lint && npm run build && npm run test && npm run test:contract"
    contract: "openapi-typescript → src/types/api.generated.ts + contract.test.ts per operationId"
  infra:
    repo: machinecare-infra
    dev_architecture: none
    gate: "—"
```

## Domain bounded contexts
`Machines`, `Maintenance`, `Attachments`

## Boundaries & projection
- BE and FE are different sides ⇒ the `Maintenance` read/write boundaries consumed by the FE are
  **`projection: cross-deploy`** → requires the **`mismagent-cross-deploy`** module.
- **contract format/location:** a single OpenAPI YAML in `architetture/api/<feature>.openapi.yaml`;
  stable `operationId`s; `components/schemas` with the **canonical domain name** (e.g. `InterventionType`).
- **authorship:** reads **consumer-driven** (the views are defined by the FE), writes
  **producer-driven** (the commands by the BE/domain); the architect arbitrates feasibility/coherence.

## Branching
- **tool:** `.claude/skills/git-branching/gitflow.sh` (a `git-branching` skill) — or `manual`
- **commit:** `"<SIDE>-<E>.<S>: <description>"` — SIDE ∈ {BE, FE}
- **model:** branch per **story** `<feature>/<E>-<S>-<slug>`; **squash** merge onto the base
  branch; the parent (docs) and `infra` commit **directly** to the base branch.

## Boundary rules
- Never **FE** code in the **BE** repo or vice versa.
- Every sub-repo has its own `.git`: `cd` inside and commit **there**, not in the parent. Use `git -C`.
- Never commit `cert/`, `.env`, `appsettings.*`, secrets, local DB files or backups.
