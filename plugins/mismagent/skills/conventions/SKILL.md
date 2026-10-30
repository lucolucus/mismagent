---
name: conventions
description: 'mismAgent craft: decides the agents'' convention proposals with the human and writes the project''s conventions skill — create or update a topic, or reject. Usage: /mismagent:conventions'
---

# /mismagent:conventions — how code is written here, decided with the human

You talk with the human. `.claude/skills/conventions/` says how each **kind of code** is written in
this repository (a message, a controller, a use case, a repository, the tests…), so builders never
reinvent one and reviewers check the same standard; agents propose in
`.mismagent/conventions-proposals.md`; the human decides; you write.

**Evidence, never invention.** Every fact you state — what the code does, a defect, what a library
can do — carries its source: a file and line you read, a command you ran now, or the human's words.
No source → it is an **assumption**, said as one.

## 1. Read
The proposals, the skill if it exists, `ARCHITECTURE.md`, and for each proposal the files it cites
and the last review of its slice. No skill yet: the first version comes from the skeleton's proposals (good principles for this
stack, each with its source); the model slice's code updates it. A **catalog** (the architect's,
ending `- now replace <topics>`): decide it kind by kind; once every line is decided, the topics it
names are replaced by the decided catalog (git keeps them) and the others stay as they are.

## 2. The proposals, as one table, then a question only where it matters
A skill with a plain `## Kinds` (`mm check` warns): first propose the split, one table of the kinds
with the category of each, accepted in one answer. Show them all first as one table — the rule in a
line, the file it shows, its category (the proposal's, default local), your recommendation —
and let the human accept in one answer those you recommend as they are. One question at a time
only for the ones you recommend to reject or reword, or that conflict. For each of those:
show the rule in one line; the code that shows it (`file:line`, a short excerpt), or before the code its source; what it changes
(a new topic, or the current rule beside the new); your recommendation and why — a conflict with
`ARCHITECTURE.md` or another topic, or a single occurrence that may be an accident. First the test: could an
acceptance test prove it (the product shows, does or refuses something)? Then it is behavior, not a
convention: say so; recommend reject (its examples keep it, a case they miss is for
`/mismagent:specify`) or a reword to only how the code does it (one seam, one module), citing the `EX-<n>`.
Then: is it a kind of code? A proposal named after a feature (export, tabs) → reword it into the
kind it shows (an adapter, a screen's model): its rules become that kind's *Must* and *Never*, what
it tells of the feature goes to the modules of `ARCHITECTURE.md`. How the work is done (doubts to a
second model, parallel worktrees) is a **practice**. Ask: create,
update, reject, or reword. The human decides, one question at a time.

## 3. Write
- `SKILL.md`: frontmatter `name: conventions`, `description: How code is written in this
  repository — load before writing or reviewing code here.`; then each kind, one line →
  `references/<kind>.md` (its *Where* in a few words), under exactly one of `## Kinds — local` (a
  kind of file: an entity, a use case, a view, an adapter), `## Kinds — cross-cutting` (rules over
  files of more than one kind: errors, security, configuration, logging, the composition root,
  naming, the layout) and `## Kinds — tests`; and `## Practices`, one line each →
  `references/practices/<practice>.md`. The category is what the release review checks: the
  hotspots of the local kinds, every cross-cutting topic along a traced path, the gate running the
  tests (`mm check` fails on a kind in no category or in two). A kind in more than one stack is one topic per stack,
  `<stack>-<kind>` (`rust-errors`, `swift-errors`).
- A kind (`mm check` fails when a section is missing):
  `## Where` (folder, file name) · `## Uses` (library, or none) · `## Shape` (a short skeleton) ·
  `## Must` · `## Never` (one checkable rule per point) · `## Example` (backticked paths, `mm check`
  fails on a missing one; until the code exists, the source). An update rewrites the topic, never
  appends a clause; a topic holding two kinds is two topics.
- A practice: `## Must` · `## Never`, one checkable rule per point (`mm check` fails without them).
- A changed rule: its reason in the change log of `ARCHITECTURE.md`; code still following the old
  rule → a line in `.mismagent/design-notes.md`.
- A slice's `## Question` waiting on a proposal: write its `## Answer` (what was decided).
- Remove every decided proposal, rejected ones too (a reason that matters later → "not: …" in its topic).
- `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" check` green; commit (`conventions`).

## 4. End
Three lines: kinds and practices created, updated, rejected. Next: `/mismagent:build`.
