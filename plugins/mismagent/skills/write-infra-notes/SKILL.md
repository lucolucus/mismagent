---
name: write-infra-notes
description: 'mismAgent explore/model: writes the project-level <output_dir>/infra-notes.md (amended, never redrafted) in the form the project''s needs dictate; each need maps to a task, enforced_by ADR or gate. Explore drafts it, the architect amends it.'
user-invocable: false
---

# MismAgent — Write Infra Notes (writer, explore/model)

Write/update `<output_dir>/infra-notes.md` — the **project's** infra notes, not the feature's:
infrastructure considerations the PRD and the contract don't cover but that generate real work in
the profile's `infra` side path. Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- → **infra blocks/tasks** (`build-manifest` / `write-task` generate them from these needs).
- → **`enforced_by` ADRs** (`write-adr`): a mechanical infra constraint (e.g. workload identity,
  no embedded secrets) becomes a versioned check the gate runs.
- → **CI gates**: the pipeline runs the sides' gates, **contract tests as a blocking job**
  and the anti-state guards (no `status:` / state files committed).
An infra need generating no task, ADR or gate is noise: **do not write it**.

## The architect's INFRA_QUESTIONS (asked, never defaulted)
Distribution and updates · workstations and connectivity · destiny of the data · retention ·
lifecycle and maintenance.

## Choose the FORM from the project's needs (the INFRA_QUESTIONS' answers)
The cloud template on a desktop app (or vice versa) produces only zombies. Sections that don't
apply **are not written**.

## Template A — hosted / cloud
```markdown
# Infra notes — <project>

## Environments & deploy
- Deploy units and environments: <dev | prod>; promotion constraints (as the architect's ADRs decide).

## Secrets & identity
- <e.g. storage via the platform's workload identity, NEVER embedded secrets> → enforced_by ADR.

## Scaling & performance (link to the PRD's NFRs)
- <e.g. NFR1 list ≤ 1.5s; rate-limiting on writes; server-side LIMIT>.

## Observability
- <structured logging, correlation-id, liveness/readiness health checks>.

## CI/CD
- Pipelines per the deploy units; contract tests = BLOCKING job; anti-state guards.

## Needs → work (what becomes a task/ADR/gate)
- <need> → <task side:infra | enforced_by ADR | CI gate>
```

## Template B — local / desktop / on-prem
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
  The templates shape the **first draft**; on any later feature **read the existing file first**
  and emit a **delta** — add this feature's infra needs, leave what other features established
  untouched. Only the **architect** amends it (explore drafts it once, when missing). Rewriting it
  per feature silently drops the architect's earlier packaging, backup, retention and update decisions.
- Every item in the final section **must** map to a task/ADR/gate, else it is a zombie.
- **Mechanical** constraints (path, identity, naming) → flag as `enforced_by` candidates for
  `write-adr`.

## Outcome
File path, infra needs listed, and for each the consumer (task side:infra / enforced_by ADR / CI
gate) that keeps it alive.
