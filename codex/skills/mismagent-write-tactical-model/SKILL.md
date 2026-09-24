---
name: mismagent-write-tactical-model
description: "mismAgent writer of the per-feature tactical-model.md: the tactical seeds and, per context, aggregates, invariants, events and commands, each row naming its reader. Invoked by mismagent-analyst and mismagent-tactical-modeler."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# mismAgent — Write Tactical Model

Write or update `<output_dir>/features/<feature>/tactical-model.md`. Invoked by `mismagent-analyst`
(the seeds) and `mismagent-tactical-modeler` (the model). Orientation: `methodology/mismagent.md`.

## Template
```markdown
# Tactical model — <feature>

> Canonical names come from `<output_dir>/context-map.md`; this file never renames them.

## Seeds for the tactical
<!-- The explore→model handoff: the analyst writes it, the tactical-modeler absorbs it and empties it. -->
- <glimpsed aggregate/invariant, one line each>

## Tactical model — <Context>
<!-- one section per context this feature touches -->
- **Aggregates / entities:** <Aggregate (root)> guards <entities / VOs>   → `aggregate` block
- **Invariants:** [INV-1] <cross-field rule>   → AC + invariant test on the aggregate block
- **Domain events:** <PastTenseEvent>   → `read-model` block / side effect / guard
- **Commands (+ actor):** <Command> (actor: <who>)   → `application-service` block
- **Seam granularity:** <entity crossing a seam: unit | aggregate-with-quantity, and its key>
- **Policy:** <when X then Y>   → side effect (omit if no reader)

## Shared Kernel
<!-- optional: only when the map declares one -->
- **Value objects:** <VO> = <meaning> (used by: <Context>, …)   → an ordinary owner block, reviewed
- **Invariants:** [INV-n] <rule on the VO>   → its invariant tests
```

## Rules
- **Feature scope:** only the contexts this feature touches; not a library that grows across features.
- Each row names its reader (the arrows); a row with no reader is not written.
- **The names are not yours:** every term is canonical in the project map, or used verbatim by the
  requirements or the brief (cite it). A new concept is a gap for the analyst, never a local coinage.
- Invariant ids (`INV-n`) are local to the feature file.

## Outcome
Path, contexts covered, seeds absorbed, terms that had to be added to the project map.
