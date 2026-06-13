---
name: mism-write-infra-notes
description: 'mismAgent''s specialized writer of infrastructure considerations (explore/model). Produces <output_dir>/<feature>/infra-notes.md in the FORM the profile dictates: cloud/cross-side (independent deploy units, secrets & identity, CI/CD) or desktop/single-side (desktop stack, local DB+migrations, backup/restore, per-OS packaging, updates). Seeds infra tasks/blocks and enforced_by ADRs. Invoked by mism-explore (draft) and mism-architect (consolidation).'
---

# MismAgent — Write Infra Notes (writer, explore/model)

Write/update `<output_dir>/<feature>/infra-notes.md`: the infrastructure considerations
that neither the PRD nor the contract cover, but that generate real work in the `infra` side's repo
(from the profile). Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- → **infra blocks/tasks** (`mism-build-manifest` / `mism-write-task` generate them from the needs
  listed here).
- → **`enforced_by` ADRs** (`mism-write-adr`): a mechanical infra constraint (e.g. Managed Identity,
  no connection strings; or: forward-only migrations) becomes a grep-rule that the
  `mism-verifier` checks.
- → **CI gates**: pipeline per side, with the **contract test as a blocking job**
  and the anti-state guards (no `status:` / state files committed).
If an infra need generates neither a task nor an ADR nor a gate, **do not write it** (it is noise).

## Choose the FORM from the profile (the declared sides decide the template)
The cloud/cross-side template on a desktop app produces only zombies (and vice versa): use the form
that matches the profile's sides. Sections that do not apply **are not written**.

## Template A — cross-side / cloud (multiple sides, cross-deploy boundaries)
```markdown
# Infra notes — <feature>

## Environments & deploy units
- INDEPENDENT deploys: one unit per side (BE, FE, sync), repo from the profile.
- Environments: <dev | prod>; promotion constraints; produces-before-consumes at deploy.

## Secrets & identity
- <e.g. Blob via Managed Identity (DefaultAzureCredential), NEVER connection strings> → enforced_by ADR.

## Scaling & performance (link to the PRD's NFRs)
- <e.g. NFR1 list ≤ 1.5s; rate-limiting on writes; server-side LIMIT>.

## Observability
- <structured logging, correlation-id, liveness/readiness health checks>.

## CI/CD
- Two independent pipelines (one per repo); contract test = BLOCKING job; anti-state guards (§1.1).

## Needs → work (what becomes a task/ADR/gate)
- <need> → <task side:infra | enforced_by ADR | CI gate>
```

## Template B — single-side / desktop / on-prem (a single side, in-process boundaries)
```markdown
# Infra notes — <feature>

## Stack & runtime
- <chosen desktop stack (architect's ADR — deliberated with the user) and its runtime constraints>.

## Local persistence
- <local DB file: where it lives, migrations (e.g. forward-only), compatibility with updates> → ADR.

## Data backup & restore
- <backup/restore strategy for the user's data — often the #1 risk of a local app> → task/ADR.

## Packaging & distribution
- <per-OS: installer/bundle, signing, distribution channel> → task.

## App updates
- <update mechanism, backwards-compatible with the schema/migrations> → task/ADR.

## Needs → work (what becomes a task/block/ADR/gate)
- <need> → <infra block/task | enforced_by ADR | gate>
```

## Rules
- Every item in the final section **must** map to a task/ADR/gate, otherwise it is a zombie.
- **Mechanical** constraints (path, identity, naming) → flag them as `enforced_by` candidates
  to be formalized with `mism-write-adr`.

## Outcome
Path of the file, infra needs listed, and for each the consumer (task side:infra / enforced_by
ADR / CI gate) that keeps it alive.
