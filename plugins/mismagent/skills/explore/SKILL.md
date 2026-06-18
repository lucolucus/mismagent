---
name: explore
description: 'mismAgent explore movement. Turns a raw idea into an understood problem + domain model, before tasks/contract/code ("no premature coding"). You dialogue in session with the user (high presence) and invoke two subagents: mismagent-challenger (demolishes the idea cold) and mismagent-analyst (models the domain and fixes the ubiquitous language that downstream gives the contract its names). Produces product-brief + context-map + spikes. No contract, no tasks here. Use at the start of a new feature.'
---

# MismAgent — Explore

mismAgent's **explore** movement: from raw idea to **understood problem** + **domain
model**. Rule: **no premature coding** — first explore and model, then plan.
Orientation: `methodology/mismagent.md`.

**Your role (high presence):** *you* dialogue in session with the user. From there you wield two
subagents as tools — they do not replace your presence, they sharpen it:
- **`mismagent-challenger`** (fresh context): tries to *demolish* the idea before you model it.
- **`mismagent-analyst`** (autonomous): models the domain and writes the `context-map.md`.

## Anti-zombie principle (what makes it mismAgent)
Keep **only** what has a **downstream consumer** (survival test). If an output has no
consumer, **do not write it**.

## Output (each with its consumer)
1. `product-brief.md` — problem, user, expected value, scope, outcome.
   → consumed by the **gate towards model**; without it, model does not start.
2. `context-map.md` — bounded contexts + relationships + **ubiquitous language** + **Seeds for the
   tactical** (persisted handoff towards `mismagent-tactical-modeler`) + open spikes.
   Written by **`mismagent-analyst`** (via `write-context-map`).
   → consumed by `mismagent-tactical-modeler` (the seeds → tactical model) and by
   **`build-manifest`** (bounded contexts → boundaries; aggregates/invariants →
   blocks; **canonical names** → types and, on cross-deploy boundaries, OpenAPI schemas via
   `create-contract`); the `mismagent-verifier` greps those terms on the diff → drift = **FAIL**,
   and demands a test for every invariant. That is why it is not a zombie.
3. **Spikes** for the unknowns → listed in `context-map.md`; in `model` they become task nodes.
4. (if needed) `infra-notes.md` (draft) via **`write-infra-notes`** → consumed in `model`.
5. (optional) `research/<topic>.md` → cited by an ADR in `model`.

## Procedure (you orchestrate the dialogue; the subagents do the autonomous work)
0. **Profile bootstrap (if missing):** explore writes into `<output_dir>` and fixes canonical names,
   so *at least* the bootstrap profile is needed. If `.mismagent/profile.md` does not exist, create it
   NOW from the `PROFILE.md` template with only the bootstrap fields: `output_dir` (default
   `.mismagent`), `ubiquitous_language.lang`, known bounded contexts, list of sides. The rest (`gate`,
   `dev_architecture`) will be finalized by the architect in `model` after the stack ADR — do NOT
   invent it.
1. **Diverge:** brainstorm the idea with the user — goals, users, constraints, alternatives.
2. **Attack the idea BEFORE modeling it:** invoke **`mismagent-challenger`** (fresh context).
   `KILL` → stop and report back to the user; `RESHAPE` → redesign with them; `PROCEED` → close the
   `MUST_ANSWER_BEFORE_MODELING` items before moving on.
3. **Model the domain:** invoke **`mismagent-analyst`** on what survived. Fix with them the
   **ubiquitous language** (one concept = one canonical name). `NEEDS-INPUT` → bring the
   `AMBIGUITIES` to the user and re-invoke.
4. **Converge on the brief:** write `product-brief.md` (problem/user/value/scope/outcome).
5. **Infra, if needed:** invoke `write-infra-notes` for the `infra-notes.md` draft.
6. **Research on-demand:** if a decision requires investigation → `research/<topic>.md`.

## Gate towards model
`model` starts **only** if `product-brief.md` (problem/user/value) **and**
`context-map.md` (at least the bounded contexts with the ubiquitous language) exist. Otherwise stay
in explore.

## Boundaries
- **No contract, no tasks, no code** in explore.
- No state artifacts. The journal is the conversation + the files produced.

## Outcome
Summary: bounded contexts (+ key ubiquitous language), problem/user/value from the brief,
**challenger's verdict**, open spikes (future task nodes), any research, and whether the gate
towards `model` is satisfied.
