---
name: conventions
description: 'mismAgent craft: decides the agents'' convention proposals with the human and writes the project''s conventions skill — create or update a topic, or reject. Usage: /mismagent:conventions'
---

# /mismagent:conventions — how code is written here, decided with the human

You talk with the human. `.claude/skills/conventions/` says how code is written in this repository;
agents propose in
`.mismagent/conventions-proposals.md`; the human decides; you write.

**Evidence, never invention.** Every fact you state — what the code does, a defect, what a library
can do — carries its source: a file and line you read, a command you ran now, or the human's words.
No source → it is an **assumption**, said as one.

## 1. Read
The proposals, the skill if it exists, `ARCHITECTURE.md`, and for each proposal the files it cites
and the last review of its slice. No skill yet: the first version comes from the model slice's code.

## 2. One proposal at a time
Show the rule in one line; the code that shows it (`file:line`, a short excerpt); what it changes
(a new topic, or the current rule beside the new); your recommendation and why — a conflict with
`ARCHITECTURE.md` or another topic, or a single occurrence that may be an accident. Ask: create,
update, reject, or reword. The human decides, one question at a time.

## 3. Write
- `SKILL.md`: frontmatter `name: conventions`, `description: How code is written in this
  repository — load before writing or reviewing code here.`; then one line per topic →
  `references/<topic>.md`, the model slice first.
- A reference, ≤ ~300 words: the rule, why, the files that show it as backticked paths (`mm check`
  fails on a missing one).
- A changed rule: its reason in the change log of `ARCHITECTURE.md`; code still following the old
  rule → a line in `.mismagent/design-notes.md`.
- Remove every decided proposal, rejected ones too (a reason that matters later → "not: …" in its topic).
- `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mm.py" check` green; commit (`conventions`).

## 4. End
Three lines: topics created, updated, rejected. Next: `/mismagent:build`.
