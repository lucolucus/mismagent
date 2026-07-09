---
name: harvest-dev-architecture
description: mismAgent build movement (optional, after the first green wave/slice). HARVESTS the side's real conventions from the code of the DONE blocks — module layout, naming, test patterns, presenter/persistence shapes, golden exemplar files — and GENERATES the side's dev-architecture skill, the "architecture memory" the profile points at and every future mismagent-worker loads. Derived from real code only (never aspirations), regenerable by re-running. Closes the QUICKSTART promise "when the patterns stabilize, write a <side>-dev-architecture skill". Use after a slice is green, or when workers start reinventing conventions.
---

# harvest-dev-architecture — from real code to architecture memory

You turn the **stabilized conventions of a side's real code** into its `<side>-dev-architecture`
skill: the per-side memory every future `mismagent-worker` loads (matrix **D**, composer-spec §13),
so patterns stop being reinvented per worker. Until now this step was a **promise nobody owned**
(QUICKSTART: *"when the patterns stabilize, write a `<side>-dev-architecture` skill"*) — you own it.

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
   - **tests** — the test shape in use (structure, fixtures, how invariant/contract tests are written);
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
6. **Point the profile at it:** set `sides.<side>.dev_architecture: <side>-dev-architecture`
   (was `none`). Tell the user the next worker dispatch will load it.

## Rules
- **Derived, regenerable:** re-running the harvest refreshes the skill from the code as it is now —
  never hand-grow the generated file (edit the code or re-harvest; the code is the source).
- **Real code only:** an unbuilt convention has no place in memory.
- **No domain content:** conventions and shapes, never business rules (those live in the blocks).

## Outcome
Summary: dimensions harvested, golden files cited, conflicts decided (and by whom), the skill path
written, the profile field updated. Consumer: **`mismagent-worker`** (matrix D) from the next dispatch.
