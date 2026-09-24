---
name: write-infra-notes
description: 'mismAgent explore/model: writes the project-level <output_dir>/infra-notes.md (amended, never redrafted) in the form the profile''s sides dictate; each need maps to a task, an enforced_by ADR or a gate. Drafted by explore, amended by the architect.'
user-invocable: false
---

# MismAgent — Write Infra Notes (writer, explore/model)

Write/update `<output_dir>/infra-notes.md` — the **project's** infra notes, not the feature's:
the infrastructure considerations
that neither the PRD nor the contract cover, but that generate real work in the `infra` side's path
(from the profile). Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- → **infra blocks/tasks** (`build-manifest` / `write-task` generate them from the needs
  listed here).
- → **`enforced_by` ADRs** (`write-adr`): a mechanical infra constraint (e.g. workload identity,
  no embedded secrets; or: forward-only migrations) becomes a versioned check the gate runs.
- → **CI gates**: pipeline per side, with the **contract test as a blocking job**
  and the anti-state guards (no `status:` / state files committed).
If an infra need generates neither a task nor an ADR nor a gate, **do not write it** (it is noise).

## The architect's INFRA_QUESTIONS (asked, never defaulted)
Distribution and updates · workstations and connectivity · destiny of the data · retention ·
lifecycle and maintenance.

## Choose the FORM from the profile (the declared sides decide the template)
The cloud/cross-side template on a desktop app produces only zombies (and vice versa): use the form
that matches the profile's sides. Sections that do not apply **are not written**.

## Template A — cross-side / cloud (multiple sides, cross-deploy boundaries)
```markdown
# Infra notes — <project>

## Environments & deploy units
- INDEPENDENT deploys: one unit per side (BE, FE, sync), path from the profile.
- Environments: <dev | prod>; promotion constraints; produces-before-consumes at deploy.

## Secrets & identity
- <e.g. storage via the platform's workload identity, NEVER embedded secrets> → enforced_by ADR.

## Scaling & performance (link to the PRD's NFRs)
- <e.g. NFR1 list ≤ 1.5s; rate-limiting on writes; server-side LIMIT>.

## Observability
- <structured logging, correlation-id, liveness/readiness health checks>.

## CI/CD
- Two independent pipelines (one per side); contract test = BLOCKING job; anti-state guards.

## Needs → work (what becomes a task/ADR/gate)
- <need> → <task side:infra | enforced_by ADR | CI gate>
```

## Template B — single-side / desktop / on-prem (a single side, in-process boundaries)
```markdown
# Infra notes — <project>

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
- **Project scope — amend, never redraft.** One infra-notes per project, in the `<output_dir>` root.
  The templates above are the shape of the **first draft**; on any later feature you **read the
  existing file first** and emit a **delta** — add what this feature's infra needs, leave everything
  another feature established untouched. Only the **architect** amends it (explore drafts it once,
  when it does not exist). Rewriting it per feature silently drops the packaging, backup, retention
  and update decisions the architect consolidated earlier.
- Every item in the final section **must** map to a task/ADR/gate, otherwise it is a zombie.
- **Mechanical** constraints (path, identity, naming) → flag them as `enforced_by` candidates
  to be formalized with `write-adr`.

## Outcome
Path of the file, infra needs listed, and for each the consumer (task side:infra / enforced_by
ADR / CI gate) that keeps it alive.
