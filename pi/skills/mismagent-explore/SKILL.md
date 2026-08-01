---
name: mismagent-explore
description: "mismAgent explore movement. Turns a raw idea into an understood problem + domain model, before tasks/contract/code (\"no premature coding\"). You dialogue in session with the user (high presence) and invoke two subagents: mismagent-challenger (demolishes the idea cold) and mismagent-analyst (models the domain and fixes the ubiquitous language that downstream gives the contract its names). Produces product-brief + context-map + spikes. No contract, no tasks here. Use at the start of a new feature."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

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

**What a "feature" is — and is NOT** (friction-log-4, open notes): a feature is a unit of
**delivery** (one manifest, one build) — not a unit of analysis, not a code module. Depth of
analysis never lives in "more features": per-context depth lives in the **tactical model**
(context-map), technology/global depth in `research/` + the ADRs + the architecture overview,
per-block depth in the manifest's **rich block files**. When the user asks for "one feature per
bounded context", they are usually asking for **depth**, not for portfolio slices — probe which
depth they want before cutting anything.

**Variability without the zombie engine:** "the system must adapt to different <instances>"
(fairs, tenants, seasons…) is legitimate **strategic** modeling — name what varies per instance
and which context owns that configuration language. The zombie enters when the *generic engine*
gets built before a **second concrete instance** exists as a consumer: model the variability's
LANGUAGE here; let the challenger attack any meta-motor whose only consumer today is hypothetical.

## Output (each with its consumer)
1. `product-brief.md` — problem, user, expected value, scope, outcome.
   → consumed by the **gate towards model**; without it, model does not start.
2. `context-map.md` — bounded contexts + relationships + **ubiquitous language** + **Seeds for the
   tactical** (persisted handoff towards `mismagent-tactical-modeler`) + open spikes.
   Written by **`mismagent-analyst`** (via `write-context-map`).
   → consumed by `mismagent-tactical-modeler` (the seeds → tactical model) and by
   **`build-manifest`** (bounded contexts → boundaries; aggregates/invariants →
   blocks; **canonical names** → types and, on cross-deploy boundaries, OpenAPI schemas via
   `create-contract`); the `mismagent-verifier`'s anti-shadow check holds the diff's domain types
   to those canonical names (cross-deploy: via the contract-generated types; in-process: a
   synonym/rename of a canonical term → **FAIL**), and it demands a test for every invariant.
   That is why it is not a zombie.
3. **Spikes** for the unknowns → listed in `context-map.md`; in `model` the **tactical-modeler
   materializes them** as `type: spike` nodes via `write-task`.
4. (if needed) `infra-notes.md` (draft) via **`write-infra-notes`** → consumed in `model`.
5. (optional) `research/<topic>.md` → cited by an ADR in `model`.

## Procedure (you orchestrate the dialogue; the subagents do the autonomous work)
0. **Profile bootstrap (ONLY if missing — it is the project's junction point, not a per-feature
   artifact):** on any feature after the first, the profile already exists: **read it, never
   re-bootstrap it**. The same holds for the whole project trunk (`context-map.md`,
   `architecture.md`, `code-rules.md`, `decisions/`) — a new feature adds a folder under
   `<output_dir>/features/`, it does not restart the project. explore writes into `<output_dir>` and fixes canonical names,
   so *at least* the bootstrap profile is needed. If `.mismagent/profile.md` does not exist, create it
   NOW from the `.agents/skills/mismagent-explore/references/PROFILE.md` template with only the bootstrap fields: `output_dir` (default
   `.mismagent`), `ubiquitous_language.lang`, known bounded contexts, list of sides,
   **`validation_mode`**, **`materials`** and **`capacity`**. The mode should surface from the dialogue itself (normal feature work, or
   a *rebuild-from-the-stated-requirements* validation run?); **if it does not surface, ask the user
   explicitly** — it decides whether challenger/analyst may treat a prior implementation of the
   deliverable as ground truth (`greenfield_from_requirements` forbids it).
   **`materials`** declares ONCE what source material exists — `sample:` (domain PDFs/screenshots)
   and `ui:` (pre-existing mockups), path or `none`: every downstream skill that names those inputs
   (analyst, researcher, challenger, ux-designer, architect) reads THIS field instead of hunting
   for folders that don't exist (friction-log-4 #3/#8). **`capacity`** declares who builds and with
   how many hours — the architect and build-manifest size stack and waves on it (friction-log-4
   #10); like the mode, **ask explicitly if they don't surface**. The rest (`gate`,
   `dev_architecture`) will be finalized by the architect in `model` after the stack ADR — do NOT
   invent it. The bounded contexts here are the **seed** ones (those you already know); the
   maintained map is the project's `<output_dir>/context-map.md` that `mismagent-analyst` writes at
   step 3 and **amends** at every later feature. The profile stays the project's **junction point**
   (output_dir, sides, gate, projections); the context-map is where the domain's names live.
1. **Diverge:** brainstorm the idea with the user — goals, users, constraints, alternatives.
2. **Attack the idea BEFORE modeling it:** invoke **`mismagent-challenger`** (fresh context).
   `KILL` → stop and report back to the user; `RESHAPE` → redesign with them; `PROCEED` → close the
   `MUST_ANSWER_BEFORE_MODELING` items before moving on.
3. **Model the domain:** invoke **`mismagent-analyst`** on what survived. Fix with them the
   **ubiquitous language** (one concept = one canonical name). `NEEDS-INPUT` → bring the
   `AMBIGUITIES` to the user and re-invoke. **If `<output_dir>/context-map.md` already exists**
   (any feature after the first), pass it to the analyst as authoritative: it **amends** the map —
   adds the contexts and terms this feature introduces, reuses the rest verbatim. A second context
   map, or a renamed term, forks the canonical names that everything downstream inherits; a rename
   that is genuinely needed goes to the user and becomes an ADR.
4. **Converge on the brief:** write `product-brief.md` (problem/user/value/scope/outcome).
5. **Infra, if needed:** invoke `write-infra-notes` for the `infra-notes.md` draft.
6. **Research on-demand:** if a decision requires investigation → `research/<topic>.md`.

## Harness read-only mode (e.g. plan mode)
If the harness forbids writes until a plan is approved, explore does **not stall** and does **not
bypass** — the conflict is only mechanical (plan mode and explore want the same thing: understand
before acting):
- the **dialogue proceeds** (it is the high-presence part) and **`mismagent-challenger` dispatches
  normally** — it is read-only by design;
- do **NOT** dispatch `mismagent-researcher` or `mismagent-analyst` while writes are forbidden:
  their handoffs are **FILES** (rule #4) and a return message is not a valid substitute — the
  work would evaporate with the context;
- the pending writes (the bootstrap profile with the answers already collected, the brief draft)
  go into the plan as an **explicit list of files to materialize**, never as replacement content;
- when writes reopen, **materializing the files is the FIRST action** (profile → brief), then
  dispatch the analyst for the context-map. The explore→model gate stays on the **files**: an
  approved plan's text is not a handoff.
`model` starts **only** if the feature's `product-brief.md` (problem/user/value) **and** the
project's `<output_dir>/context-map.md` (at least the bounded contexts this feature touches, with
their ubiquitous language) exist. Otherwise stay
in explore.

## Boundaries
- **No contract, no tasks, no code** in explore.
- No state artifacts. The journal is the conversation + the files produced.

## Outcome
Summary: bounded contexts (+ key ubiquitous language), problem/user/value from the brief,
**challenger's verdict**, open spikes (future task nodes), any research, and whether the gate
towards `model` is satisfied.
