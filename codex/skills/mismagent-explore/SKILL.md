---
name: mismagent-explore
description: "mismAgent intent: explores a new idea before anything is specified \u2014 a dialogue on the problem, the brief, the challenger's attack, then an event storm of the domain with its hotspots. Usage: $mismagent-explore <idea in one sentence>"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# $mismagent-explore — understand the idea before building it

For a new product or a large new part of one. You talk with the human; you are curious and
skeptical, never a stenographer. Idea: <the argument this skill was invoked with>

**Evidence, never invention.** Every fact you state — a number (a limit, a size, a price, a
volume, a timing), what a language, library, model or platform can or cannot do, a defect, how
existing code behaves — carries its source: a file and line you read, the output of a command you
ran now, a page you fetched (its URL), or the human's words. No source → it is not a fact: write it
as an **assumption** with how to check it (a question, a hotspot, a probe you can run), or leave it
out. A guess presented as a fact is a defect.

The work lives on disk and survives a new session: read `.mismagent/brief.md` and
`.mismagent/event-storm.md` first, and resume where they stop.

## 1. The problem
Ask, a few questions at a time, each with your guess so the human can just confirm:
who has the problem, when and where it bites; how they cope today (and what that costs them); what
"better" looks like in their words; who else is touched; what must not change; the materials that
exist (requirements, forms, screenshots, an old system). Then write `.mismagent/brief.md`, one page:
problem · users and their context · value · in scope · out of scope · open questions.

## 2. The challenger
Dispatch **mismagent-challenger** with the path of the brief. Show the human its verdict and its
attacks, with your own view of each. **The human decides**: stop (KILL), change the brief (RESHAPE,
then challenge again if the change is large), or go on (PROCEED). Record the decision and why at
the end of the brief.

## 3. The event storm (Brandolini, in text)
Rebuild the domain as a **timeline of events**, in the past tense, in the human's words ("Sale
opened", "Item added", "Payment received", "Day closed"). Propose a first timeline from the
brief, then walk it with the human, event by event:
- the **command** that causes it and the **actor** who issues it;
- the **policy** that reacts to it ("whenever a day is closed, the report is printed");
- the **read model** someone looks at to decide (a screen, a report, a receipt);
- an **external system** involved, if any;
- **can it be undone? by whom? what remains of it?** — a correction is a new event, never an
  erasure: this question alone finds refunds, voids, audit and end-of-day rules a story skips.

Every doubt, conflict, gap or "it depends" becomes a **hotspot**. Where the same word means two
things, or two words mean one, note it: it is where a boundary between contexts runs.

Write `.mismagent/event-storm.md`:
```
## Timeline
| # | event | command | actor | policy | read model | undo |
## Hotspots
- H1: <the question> — <who can answer>
## Language
- <term>: <meaning> (context)
```
Keep it at the level of the whole process: no screens in detail, no data model, no code. The detail
comes one release at a time, in `$mismagent-specify`.

## 4. Close
Ask the human for a first release cut: which part of the timeline, end to end, is the smallest thing
worth using. Write it under `## First release` in the brief. Commit (`explore`) and end your last
message with `EXPLORED`. Next: `$mismagent-specify R0`, which turns that part of the timeline into
examples and slices, and the hotspots into its first questions.

## Never
Choose the stack, write examples, slices or code, or decide a hotspot the human has not answered.
