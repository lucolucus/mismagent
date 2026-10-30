# mismAgent plugin — 0.7

Guides agents to write software that **stays maintainable** over long projects. The code carries
the theory of the program (Naur); XP keeps it clean; the human agrees concrete examples; the
harness keeps both honest. Design: `docs/rationale/v0.5-vision.md` at the repository root.

**Requires** Claude Code and Python 3 (standard library only: `mm`, the hooks) — the same choice as
BMad.

## Use
```
/mismagent:explore <idea>        # a new product: the problem, the brief, the challenger, the event storm
/mismagent:specify <request>     # investigative interview → examples + slices for the next release
/mismagent:build                 # one action: build, review, land, design pass, or stop for you
/mismagent:build --confirm R0    # your confirmation of a release → the tag (--why "…" over a DESIGN-PASS review: recorded as a decision)
/mismagent:conventions           # decide the agents' convention proposals → the project's conventions skill
/mismagent:site                  # the project in the browser: releases as swimlanes, requirements → examples → tests
```
Or leave `/loop /mismagent:build` running in a session of its own: the always-on conductor. It does
every action as soon as it is ready (build, review, land, design pass); when it needs you it waits,
checking back every ten minutes, and resumes by itself once you have answered. It notifies you
when it stops for you (`NEEDS-HUMAN`) or has something you should know (`FOR-HUMAN`). Talk to it
there, or from another session with `SendMessage`: it answers first, then runs a review, a
challenge or a design pass you ask for as its next action. Sonnet is enough for that session (the
agents run on their own models); work in another checkout, or it waits while the tree is dirty.

## Contents
| piece | role |
|---|---|
| `skills/explore` + `agents/mismagent-challenger` | a new idea: dialogue on the problem → `brief.md`; a fresh adversary tries to kill it; an event storm of the domain with its hotspots → `event-storm.md` |
| `skills/specify` | intake, the stack review (architect and challenger in parallel, confronted Socratically with the human), the investigation rule by rule, examples, vertical slices — one release at a time |
| `commands/build.md` | the conductor: asks `mm next`, does exactly one action, settles doubts, stops for the human |
| `agents/mismagent-architect` | `stack` (options from the problem's forces, blind to the human's preference) · `skeleton` (structure at birth: `ARCHITECTURE.md`, error policy, sensors, the model slice, the first conventions from the stack's good principles) · `design-pass` (from the code: refactoring slices) · `escalate` |
| `agents/mismagent-builder` | one slice: acceptance tests first at the use-case seam, TDD, refactoring, a commit at every green |
| `agents/mismagent-reviewer` | a fresh reviewer on the review table: a slice's diff, or a release (the code it touched and the paths it runs through, the app run) |
| `skills/craft` | the XP inner loop and its references, incl. `review-table.md` |
| `skills/conventions` | with the human: the agents' proposals → `.claude/skills/conventions/` (how code is written in the project) |
| `tools/mm.py` | computes and moves: `status`, `next`, `start`, `park`, `built` (the gate with the slice's Base: what the reviewer will check), `review`, `shot`, `land`, `gate`, `tag` (a review at HEAD; `--why` over a DESIGN-PASS), `check` |
| `tools/mmsite.py` + `mmsite_live.py` + `mmsite.html` | read-only: one live HTML page of the project, served on 127.0.0.1 — releases as swimlanes, requirements → examples → slices → tests, conventions, decisions (`/mismagent:site`) |
| `hooks/` | agents never merge, tag, switch branches or move state; never edit what the human owns (requirements, examples, artboards, the conventions skill); a desktop notification when the conductor stops for the human (`MISMAGENT_NOTIFY` to send it elsewhere) |

## In a project
`ARCHITECTURE.md` and `CLAUDE.md` (section `## mismagent`: test, lint, smoke, shot, thresholds, `timeout` for a gate that may hang) at the root;
`.claude/skills/conventions/` (the project's conventions, yours);
`tests/acceptance/` (one test per example, marker `EX-<n>`; elsewhere with `acceptance:`);
`.mismagent/`, one thing per file: `brief.md` (one page), `event-storm.md`, `releases/<R>.md`
(scope, open questions — a release is reviewed and tagged only with none open; a question that
waits for a later release is written in that release's file), `examples/<capability>.md`, `design/` (the approved artboards, as images),
`decisions/NNNN-<name>.md`,
`slices/{todo,doing,done}/` (each with its `## Progress`), `reviews/`, `shots/` (the app's screens
beside their artboards), `design-notes.md`,
`conventions-proposals.md`.

The v0.26 flow (explore/model/worker-composer) is in `attic/v0.26/`.
