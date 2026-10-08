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
/mismagent:build --confirm R0    # your confirmation of a release → the tag
/mismagent:conventions           # decide the agents' convention proposals → the project's conventions skill
```
Or leave `/loop /mismagent:build` running in a session of its own: the always-on conductor. It does
every action as soon as it is ready (build, review, land, design pass); when it needs you it waits,
checking back every ten minutes, and resumes by itself once you have answered.

## Contents
| piece | role |
|---|---|
| `skills/explore` + `agents/mismagent-challenger` | a new idea: dialogue on the problem → `brief.md`; a fresh adversary tries to kill it; an event storm of the domain with its hotspots → `event-storm.md` |
| `skills/specify` | intake, the stack review (architect and challenger in parallel, confronted Socratically with the human), the investigation rule by rule, examples, vertical slices — one release at a time |
| `commands/build.md` | the conductor: asks `mm next`, does exactly one action, settles doubts, stops for the human |
| `agents/mismagent-architect` | `stack` (options from the problem's forces, blind to the human's preference) · `skeleton` (structure at birth: `ARCHITECTURE.md`, error policy, sensors, the model slice) · `design-pass` (from the code: refactoring slices) · `escalate` |
| `agents/mismagent-builder` | one slice: acceptance tests first at the use-case seam, TDD, refactoring, a commit at every green |
| `agents/mismagent-reviewer` | a fresh reviewer on the review table: a slice's diff, or the whole release |
| `skills/craft` | the XP inner loop and its references, incl. `review-table.md` |
| `skills/conventions` | with the human: the agents' proposals → `.claude/skills/conventions/` (how code is written in the project) |
| `tools/mm.py` | computes and moves: `status`, `next`, `start`, `park`, `land`, `gate`, `tag`, `check` |
| `hooks/` | agents never merge, tag, switch branches or move state; never edit what the human owns (requirements, examples, the conventions skill) |

## In a project
`ARCHITECTURE.md` and `CLAUDE.md` (section `## mismagent`: test, lint, smoke, thresholds) at the root;
`.claude/skills/conventions/` (the project's conventions, yours);
`tests/acceptance/` (one test per example, marker `EX-<n>`); `.mismagent/`: `brief.md`, `event-storm.md`,
`examples.md`, `slices/{todo,doing,done}/`, `reviews/`, `progress.md`, `design-notes.md`,
`decisions/`, `conventions-proposals.md`.

The v0.26 flow (explore/model/worker-composer) is in `attic/v0.26/`.
