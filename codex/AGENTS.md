# mismAgent — Codex packaging

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

> **Codex mapping (this packaging).** The commands are Codex **skills**: `$mismagent-explore`,
> `$mismagent-specify`, `$mismagent-build`, `$mismagent-conventions` (or `/skills`). The agents are
> Codex **subagents** in `.codex/agents/`, spawned by `$mismagent-build` and `$mismagent-explore`.
> The project's own conventions skill lives in `.agents/skills/conventions/`, and the project's
> settings (`## mismagent`: test, lint, smoke, thresholds) in this `AGENTS.md`. The Claude Code
> hooks are not shipped: the prompts and `mm check` hold their rules.

**Setup (once).** From the mismagent repo: `codex/install.sh <your-project-root>`. It copies the
skills into `<project>/.agents/skills/`, the subagents into `<project>/.codex/agents/`, and this
file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists: merge it), and
anchors every tool path to the absolute installed skills directory (re-run it after moving the
project). Requires Python 3 (standard library only) for `mm`. Verify: `/skills` lists
`mismagent-build`.


Guides agents to write software that **stays maintainable** over long projects. The code carries
the theory of the program (Naur); XP keeps it clean; the human agrees concrete examples; the
harness keeps both honest. Design: [`v0.5-vision.md`](https://github.com/lucolucus/mismagent/blob/master/docs/rationale/v0.5-vision.md).

## Use
```
$mismagent-explore <idea>        # a new product: the problem, the brief, the challenger, the event storm
$mismagent-specify <request>     # investigative interview → examples + slices for the next release
$mismagent-build                 # one action: build, review, land, design pass, or stop for you
$mismagent-build --confirm R0    # your confirmation of a release → the tag
$mismagent-conventions           # decide the agents' convention proposals → the project's conventions skill
```

## Contents
| piece | role |
|---|---|
| `mismagent-explore` skill + `mismagent-challenger` agent | a new idea: dialogue on the problem → `brief.md`; a fresh adversary tries to kill it; an event storm of the domain with its hotspots → `event-storm.md` |
| `mismagent-specify` skill | intake, the stack review (architect and challenger in parallel, confronted Socratically with the human), the investigation rule by rule, examples, vertical slices — one release at a time |
| `mismagent-build` skill | the conductor: asks `mm next`, does exactly one action, settles doubts, stops for the human |
| `mismagent-architect` agent | `stack` (options from the problem's forces, blind to the human's preference) · `skeleton` (structure at birth: `ARCHITECTURE.md`, error policy, sensors, the model slice) · `design-pass` (from the code: refactoring slices) · `escalate` |
| `mismagent-builder` agent | one slice: acceptance tests first at the use-case seam, TDD, refactoring, a commit at every green |
| `mismagent-reviewer` agent | a fresh reviewer on the review table: a slice's diff, or the whole release |
| `mismagent-craft` skill | the XP inner loop and its references, incl. `review-table.md` |
| `mismagent-conventions` skill | with the human: the agents' proposals → `.agents/skills/conventions/` (how code is written in the project) |
| `mismagent-build/scripts/mm.py` | computes and moves: `status`, `next`, `start`, `park`, `land`, `gate`, `tag`, `check` |

## In a project
`ARCHITECTURE.md` and `AGENTS.md` (section `## mismagent`: test, lint, smoke, thresholds) at the root;
`.agents/skills/conventions/` (the project's conventions, yours);
`tests/acceptance/` (one test per example, marker `EX-<n>`; elsewhere with `acceptance:`);
`.mismagent/`, one thing per file: `brief.md` (one page), `event-storm.md`, `releases/<R>.md`
(scope, open questions), `examples/<capability>.md`, `decisions/NNNN-<name>.md`,
`slices/{todo,doing,done}/` (each with its `## Progress`), `reviews/`, `design-notes.md`,
`conventions-proposals.md`.
