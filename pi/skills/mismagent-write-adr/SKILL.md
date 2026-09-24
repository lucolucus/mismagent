---
name: mismagent-write-adr
description: "mismAgent model: writes <output_dir>/decisions/NNNN-<slug>.md (scope, status, supersedes, closes_spike) and, for mechanical constraints, enforced_by versioned checks run by the gate. Invoked by the architect, create-contract, write-infra-notes."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# write-adr — decisions that something enforces

Write an ADR in `<output_dir>/decisions/NNNN-<slug>.md` (4-digit number, the next free one).
`MM pack` carries it to the worker and the reviewers; the **gate** runs its checks; the
**code-review** judges discursive ADRs.

## Template
```markdown
---
scope: global | <side> | infra
status: proposed | accepted | superseded
supersedes: <NNNN-slug>          # only when it replaces one
closes_spike: <spike-slug>       # only when it answers one
enforced_by:                     # only for mechanical constraints
  - check: <path of the check, relative to the repo>
    from: <block-id>             # optional: the block that makes it applicable
---
# NNNN — <decision>

## Context
## Decision
## Consequences
```

## enforced_by — versioned checks, never shell strings
A **mechanical** constraint (dependency direction, a confined write, presence or absence of a
construct) gets a **check**: a file in the project repo, run by the side's **gate**.
Judgment → no `enforced_by`: the code-review's. Dependency rules go to the gate's
dependency lint (`write-code-rules`), cited as the check.

Each check:
- lives in the repo with a **violating fixture it must fail on** and a **conforming fixture it must
  pass on**, and runs on both inside the gate — that is its red-green proof;
- is **registered in the gate** and prints a recognizable result naming the ADR
  (`ADR-NNNN <check>: PASS|FAIL`); the gate files it adds join the profile's `gate_files`,
  renewing the gate proof;
- matches **code, not text**: a comment or a test-fixture string naming the construct neither
  violates a prohibition nor satisfies a presence — the fixtures include both cases;
- covers the **alternative violations**: list the idiomatic ways to break the rule and put each in
  the violating fixture;
- targets modules/packages or symbols the architecture fixes, never a guessed filename, and **fails
  when its applicable target is missing** (a fixture proves it: a scan over nothing is not green);
- runs with a **declared interpreter/toolchain** (no implicit shell, no GNU-only tools) and is
  validated invoked **exactly as the gate invokes it**, quoting included.

**Presence and prohibition are separate checks.** A prohibition applies from the start (no `from`:
the wave-0 scaffold writes it, or it already exists). A presence is red until its block exists:
give it `from: <block-id>` — that block writes the check and registers it, and the check applies
from that block's own review onward (`from` may name a block of any feature). `MM lint` checks
existence and `from`.

**Migration:** a legacy `enforced_by` string (or an old `kind`/`rule` entry) is never executed —
`MM lint` reports it; rewrite it as checks.

## Rules
- **A key implies uniqueness:** an ADR electing a field as a lookup/correlation/decode key names
  the uniqueness invariant (`[INV-n]` + its test) on the aggregate publishing it, or states why it
  holds by construction.
- **Supersede:** set `status: superseded` on the old ADR and link it.
- **Closing a spike, both directions:** `closes_spike` here **and** `[x]` on the context-map entry
  (and its node to `done/`) in the same pass.
- **Reconcile before finalizing:** a context-map line contradicting the decision is updated in the
  same pass; a mechanism colliding with a profile boundary rule is surfaced as a decision (scope an
  exception or drop the mechanism) — never left for a worker.
- **Breaking contract change:** fix the versioning protocol first and create (via `write-task`) a
  `type: cleanup` node with `ready_when: "no-consumer-uses:<operationId>"`.

## Outcome
Path, number, scope; its checks (path, `from`) or "discursive → code-review".
