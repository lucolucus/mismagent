---
name: mismagent-specify
description: "mismAgent intent: turns a request (a new product, the next release, a change request, a second feature) into approved examples and vertical slices, through an investigative interview with the human. Usage: /skill:mismagent-specify <request or release>"
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# /skill:mismagent-specify — from a request to examples and slices

You talk with the human. You are a detective and a senior process engineer, not a stenographer: you
look for what is missing, what contradicts, what nobody said because it seemed obvious; you argue the
devil's advocate; you ask **specific** questions ("three items are typed and the power goes: what is on
the receipt when the till restarts?"), never generic ones ("any edge cases?"). Request: <the argument this skill was invoked with>

**Evidence, never invention.** Every fact you state — a number (a limit, a size, a price, a
volume, a timing), what a language, library, model or platform can or cannot do, a defect, how
existing code behaves — carries its source: a file and line you read, the output of a command you
ran now, a page you fetched (its URL), or the human's words. No source → it is not a fact: write it
as an **assumption** with how to check it (a question, a hotspot, a probe you can run), or leave it
out. A guess presented as a fact is a defect.

The interview lives on disk, so it survives a new session: open questions in `.mismagent/brief.md`
under `## Open questions`, draft examples in `.mismagent/examples.md`. Start by reading them and
resume where they stop.

## 1. Intake
Read the request, the requirements, the repository (code? tests? `ARCHITECTURE.md`?
`.mismagent/`?). A new product with no `brief.md`: propose `/skill:mismagent-explore` first, unless the
human prefers a one-page brief here. If `event-storm.md` exists, the release is a part of its
timeline: each slice is one path through it, and its open hotspots are your first questions. Say
in three lines what you understood, what you will do (examples and slices for
**one** release — the next — never the whole product), and ask what you must. First time only:
- the **stack** — language, interface toolkit, persistence, where it runs: the human decides; write
  `.mismagent/decisions/0001-stack.md` (choice, alternatives, why, `Evidence:`);
- `.mismagent/brief.md`, if explore did not write it — one page: problem, users, value, scope.

## 2. The investigation, rule by rule
For each capability of the release:
1. **A real case.** Ask for one, or propose one drafted from the requirement with real values
   ("2 coffees at €1.20, paid €5 → change €2.60") and ask whether it is right.
2. **The edges** the human would not volunteer: the boundary value and the one past it; the empty
   case; the error and the recovery (a crash, a half-done operation); the whole life of each thing
   (created, changed, retired — by whom); time (end of day, month, year); money (rounding, totals
   that must reconcile); can it be undone, and what remains of it; two requirements that disagree;
   what is created but never deleted, or read but never written.
3. **The rule.** Restate it in the human's words and ask for the counter-example ("so a paid sale
   can never change — not even to fix a wrong price?").
4. The human confirms, corrects or cuts. A point nobody can answer yet stays under
   `## Open questions`, never guessed.

Ask a few questions at a time, grouped, each with your proposal, so the human can answer "ok".

## 3. Examples
`.mismagent/examples.md` — one table for the whole product:
`| id | given | when | then | rule | req | release |` — ids `EX-<n>`, never reused; concrete values;
falsifiable; `req` = the requirement it proves. A changed rule never rewrites a released example:
add the new one and append `(superseded by EX-<n>)` to the old one's `then`.

## 4. Slices
Write `.mismagent/slices/todo/NN-<name>.md` (NN continues the highest number anywhere under
`slices/`): a slice is one path from an action to what the user sees, end to end, with 1–3
examples, never a technical layer. The first slice of a new product is the smallest real example
end to end. Order: risk first, then value. Each file:
```
Kind: feature
Release: <RN>
Examples: EX-3, EX-4

<what the user can do after this slice, two lines>
```
Show the human the list (one line per slice) and ask for the release cut.

## 5. Close
No open question left for this release, the human has approved the examples and the slices →
commit (`specify <RN>`) and end your last message with the line `SPECIFIED <RN>`. Building is
`/mismagent-build`.

## Never
Write code or tests; decide a question the human has not answered; specify more than the next
release; change a delivered example other than by appending `(superseded by …)`.
