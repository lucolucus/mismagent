# mismAgent — pi packaging

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

> **pi mapping (this packaging).** `/mismagent-build` is a **prompt template**; the other commands
> are pi **skills**: `/skill:mismagent-explore`, `/skill:mismagent-specify`,
> `/skill:mismagent-conventions`. The agents are definitions in `.pi/agents/` for the `subagent`
> tool, which `/mismagent-build` and the explore skill call with `agentScope: "both"`. The
> project's own conventions skill lives in `.agents/skills/conventions/`, and the project's
> settings (`## mismagent`: test, lint, smoke, thresholds) in this `AGENTS.md`. The Claude Code
> hooks are not shipped: the prompts and `mm check` hold their rules. pi has no per-agent reasoning
> knob: to make the challenger, the reviewer and the architect think harder, pin a stronger
> `model:` in their `.pi/agents/*.md`.

**Setup (once).** From the mismagent repo: `pi/install.sh <your-project-root>`. It copies the
skills into `<project>/.agents/skills/`, the prompt template into `<project>/.pi/prompts/`, the
agent definitions into `<project>/.pi/agents/`, and this file as the project's `AGENTS.md` (or
`AGENTS.mismagent.md` if one already exists: merge it), and anchors every tool path to the
absolute installed skills directory (re-run it after moving the project). The agents need pi's
official `subagent` example extension (pi repo,
`packages/coding-agent/examples/extensions/subagent/`: symlink `index.ts` and `agents.ts` into
`~/.pi/agent/extensions/subagent/`). Requires Python 3 (standard library only) for `mm`. Verify:
`/mismagent-build` autocompletes. Alternative global install (skills and prompts only):
`pi/install.sh --package <dir>`, then `pi install <dir>`.


Guides agents to write software that **stays maintainable** over long projects. The code carries
the theory of the program (Naur); XP keeps it clean; the human agrees concrete examples; the
harness keeps both honest. Design: [`v0.5-vision.md`](https://github.com/lucolucus/mismagent/blob/master/docs/rationale/v0.5-vision.md).

## Use
```
/skill:mismagent-explore <idea>        # a new product: the problem, the brief, the challenger, the event storm
/skill:mismagent-specify <request>     # investigative interview → examples + slices for the next release
/mismagent-build                 # one action: build, review, land, design pass, or stop for you
/mismagent-build --confirm R0    # your confirmation of a release → the tag
/skill:mismagent-conventions           # decide the agents' convention proposals → the project's conventions skill
```

## Contents
| piece | role |
|---|---|
| `mismagent-explore` skill + `mismagent-challenger` agent | a new idea: dialogue on the problem → `brief.md`; a fresh adversary tries to kill it; an event storm of the domain with its hotspots → `event-storm.md` |
| `mismagent-specify` skill | intake, stack, the investigation rule by rule, examples, vertical slices — one release at a time |
| `mismagent-build` skill | the conductor: asks `mm next`, does exactly one action, settles doubts, stops for the human |
| `mismagent-architect` agent | `skeleton` (structure at birth: `ARCHITECTURE.md`, error policy, sensors, the model slice) · `design-pass` (from the code: refactoring slices) · `escalate` |
| `mismagent-builder` agent | one slice: acceptance tests first at the use-case seam, TDD, refactoring, a commit at every green |
| `mismagent-reviewer` agent | a fresh reviewer on the review table: a slice's diff, or the whole release |
| `mismagent-craft` skill | the XP inner loop and its references, incl. `review-table.md` |
| `mismagent-conventions` skill | with the human: the agents' proposals → `.agents/skills/conventions/` (how code is written in the project) |
| `mismagent-build/scripts/mm.py` | computes and moves: `status`, `next`, `start`, `land`, `gate`, `tag`, `check` |

## In a project
`ARCHITECTURE.md` and `AGENTS.md` (section `## mismagent`: test, lint, smoke, thresholds) at the root;
`.agents/skills/conventions/` (the project's conventions, yours);
`tests/acceptance/` (one test per example, marker `EX-<n>`); `.mismagent/`: `brief.md`, `event-storm.md`,
`examples.md`, `slices/{todo,doing,done}/`, `reviews/`, `progress.md`, `design-notes.md`,
`decisions/`, `conventions-proposals.md`.
