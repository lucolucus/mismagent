---
name: mismagent-harvest-dev-architecture
description: "mismAgent build: harvests the real conventions of DONE, green code (layout, naming, tests, per-type patterns, golden files) into the dev-architecture memory workers load; lessons mode appends per-type review lessons. Use after a green slice."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# harvest-dev-architecture — from real code to architecture memory

You turn a codebase's **real** conventions into its dev-architecture skill: the memory every
`mismagent-worker` loads, so patterns stop being reinvented.

**You are the descriptive route.** In greenfield the architect may already have **authored** the
memory before the first domain wave (the profile's `dev_architecture` points at it). You ground it
in the code: the code confirms, refines or contradicts it — contradictions are decisions for the
user — and you update **that same** memory, never a second copy.

## Full harvest

**Preconditions:** at least one wave/slice of the side is `done` and green (one block is an
anecdote — too early → say so and stop); the profile names the side and path.

1. **Read the done blocks' code only** (`blocks/<ctx>/done/` names them). Harvest what **is**,
   never what should be.
2. **Extract one section per dimension, each with 1–2 golden exemplar files by path:** layout
   (packages/modules as built) · naming (the real suffixes, test names, port vs adapter) · tests
   (shape, fixtures, how invariant/contract tests are written; a naming convention with forbidden
   characters lists **all** of them — a partial list induces the error it should prevent) ·
   patterns per block type (presenter/view split, persistence shape, errors at the seams) ·
   toolchain quirks keeping the gate green.
3. **Conflicts are decisions, not averages:** two competing patterns → the user picks the canonical
   one; flag the other exemplars as legacy.
4. **The user confirms the summary before you write** — it binds every future worker.
5. **Write** `<side>-dev-architecture/SKILL.md` in the harness's project-skill directory, with a
   GENERATED-BY banner (this skill + date). Keep it small: rules + golden-file paths. **One memory
   per codebase**, not per side: sides sharing one codebase share one memory.
6. **Point the profile at it:** `sides.<side>.dev_architecture`, the same value for every side
   sharing the codebase. Tell the user the next dispatch loads it.

## Lessons mode — one block type, dispatched by the worker-composer

When the first block of a type passes review, or a rework fixed a defect the next block of that
type could repeat. No slice precondition: one review finding and its fix are enough. Input: block
id, type, findings, the `rework/<id>-<n>.md` files.

1. Keep only what **generalizes to the type**: the defect class + the fixing pattern + the golden
   file — *"<type>: <what must always hold> — see `<golden file>`"*. A one-off bug is not a lesson.
2. Append it under **`## <type>`** (the exact block type, e.g. `## application-service` — the
   heading `MM pack` reads) in `<output_dir>/architetture/lessons-by-block-type.md`, one list item
   of 1–3 lines, deduplicated. The file is not the memory: it survives every regeneration.
3. **No blocking checkpoint:** the composer reports the lessons; the user strikes (`~~…~~`) any
   they reject, and a struck lesson is no longer packed. A lesson contradicting the memory is not
   written — it is a conflict for the user.
4. A full harvest may promote a lesson the code now embodies everywhere into the memory; it never
   deletes or rewrites the lessons file.

## Rules
- **Derived, regenerable:** re-harvest instead of hand-editing the generated skill. The lessons
  file is the exception: a review history the code cannot re-derive.
- **Real code only; no business rules.**

## Outcome
Dimensions, golden files, conflicts decided (by whom), skill path, profile field — or the
lessons appended per type.
