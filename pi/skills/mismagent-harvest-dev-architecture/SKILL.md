---
name: mismagent-harvest-dev-architecture
description: "mismAgent build movement (optional, after the first green wave/slice). HARVESTS the codebase's real conventions from the code of the DONE blocks \u2014 module layout, naming, test patterns, presenter/persistence shapes, golden exemplar files \u2014 and GENERATES the dev-architecture skill, the \"architecture memory\" the profile points at and every future mismagent-worker loads. The DESCRIPTIVE route: derived from real code only (never aspirations), regenerable by re-running; the PRESCRIPTIVE route is the architect's authored doc BEFORE the first domain wave, which this harvest later grounds/reconciles against the real code. One memory per CODEBASE (not per deploy role). Use after a slice is green, or when workers start reinventing conventions."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# harvest-dev-architecture — from real code to architecture memory

You turn the **stabilized conventions of a codebase's real code** into its dev-architecture
skill: the memory every future `mismagent-worker` loads (matrix **D**, composer-spec §13),
so patterns stop being reinvented per worker. Until now this step was a **promise nobody owned**
(QUICKSTART: *"when the patterns stabilize, write a `<side>-dev-architecture` skill"*) — you own it.

**You are the DESCRIPTIVE route — an AUTHORED memory may already exist** (friction-log-4 #21/#27):
in greenfield the **architect authors** the dev-architecture *before* the first domain wave
(deliberated with the user; the profile's `dev_architecture` points at the doc, the
worker-composer injects it into every dispatch). You are the harvest that **grounds/refreshes**
the memory once real code exists: the code confirms, refines or contradicts the authored rules —
contradictions are **decisions for the user** (rule 3 below), and the outcome updates the SAME
memory the profile points at, never a second fork of it.

## Preconditions (don't harvest noise)
- At least **one wave/slice of the side is green** (`done` blocks exist and the gate passes).
  One block is anecdote, a slice is a pattern. If it's too early, say so and stop.
- The **active profile** (`<output_dir>/profile.md`) names the side and its repo.

## Procedure
1. **Read the DONE blocks' code** (only theirs — `blocks/<ctx>/done/` names them; the code is in the
   side's repo). You harvest what **is**, never what *should be*: no aspiration enters the memory.
2. **Extract, one section per dimension, each with 1–2 GOLDEN exemplar files cited by path:**
   - **layout** — module/package structure as actually built (contexts → packages);
   - **naming** — the real conventions (suffixes like `...SqlDelight`, test names, port vs adapter);
   - **tests** — the test shape in use (structure, fixtures, how invariant/contract tests are
     written); if test names use backticks, state the **full** JVM-illegal char list
     `[ ] . ; : / < >` — an incomplete "forbidden chars" list *induces* the compile error it
     should prevent (friction-log-4 #33);
   - **patterns per block-type** — the presenter/thin-view split as implemented, the adapter's
     persistence shape, error handling at the seams;
   - **toolchain quirks** — anything a worker must know to keep the gate green (from the profile's
     `toolchain` + what the scaffold learned).
3. **Conflicts are decisions, not averages:** two competing patterns in the code → bring both to the
   user, they pick the canonical one, record the choice (and flag the non-canonical exemplars as
   legacy). Never harvest an inconsistency as if it were a rule.
4. **Present the harvest summary to the user before writing** — these conventions become **binding**
   for every future worker; the user confirms (high presence on the *what holds*, as with `tests_nl`).
5. **Write the skill** `<side>-dev-architecture/SKILL.md` in the harness's project-skill directory
   (Claude Code: `.claude/skills/`; Codex: `.agents/skills/`), with a GENERATED-BY banner naming this
   skill and the harvest date. Keep it **small** (the worker pays its context every dispatch): rules +
   golden-file paths, not prose essays — the exemplar files carry the detail.
   **The memory attaches to the CODEBASE, not the deploy role** (friction-log-4 #23): sides that
   share one domain codebase get ONE shared memory (per-side copies would describe the same
   files; what varies per role is only the `app-<role>` wiring, already guarded by its
   prohibition `enforced_by`s). Harvest per-side only when the sides really are separate codebases.
6. **Point the profile at it:** set `sides.<side>.dev_architecture` — for **every** side sharing
   the codebase, to the **same** value (was `none`, or the authored doc you just reconciled).
   Tell the user the next worker dispatch will load it.

## Rules
- **Derived, regenerable:** re-running the harvest refreshes the skill from the code as it is now —
  never hand-grow the generated file (edit the code or re-harvest; the code is the source).
- **Real code only:** an unbuilt convention has no place in memory.
- **No domain content:** conventions and shapes, never business rules (those live in the blocks).

## Outcome
Summary: dimensions harvested, golden files cited, conflicts decided (and by whom), the skill path
written, the profile field updated. Consumer: **`mismagent-worker`** (matrix D) from the next dispatch.
