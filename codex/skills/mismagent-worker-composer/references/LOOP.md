# The build loop — design (v0.16)

**The tool computes; the composer follows a short, linear procedure; in doubt it stops and asks.**
No state engine, no automatic crash recovery: safety comes from refusing, not from guessing.

## Constraints
- **One repository per project.** A side is a code/verification scope **inside** it (a path),
  never a repo of its own. The integration line is one branch of that repo; `F` is committed on it, in one checkout
  of it — state and code never land on different branches.
- **Build in parallel, integrate in series.** Independent ready blocks build at once (each in its own
  worktree, up to the profile's cap); review → candidate merge → promote happen **one block at a
  time**.
- **Only exact checks in code**; judgment stays with agents and the user.
- **No timeouts, no watchdogs, no revert.** A promote happens only for a reviewed sha whose gate and
  contract tests passed on the candidate.

## State = files (all under `F` = `<output_dir>/features/<feature>/`)
| file | meaning | written by |
|---|---|---|
| `blocks/<ctx>/{todo,doing,done}/<id>.md` | the block's phase | `MM move` |
| `open-questions/<id>.md` | parked: a question for the user | composer; deleted by `build-manifest` when answered, after it records the answer in `decisions.md` |
| `rework/<id>-<n>.md` | the findings of rework cycle n (the cap counts these files) | composer |
| `review-proof/<id>.json` | reviewed `sha` + `spec_hash` | `MM proof record F review <id> --sha S --spec-hash H` |
| `integrated/<id>.json` | promoted: the block's sha is on the integration line | `MM compose promote F <id>` |
| `gate-proof/<side>/proof.json` | the gate's red-green proof (project fact) | `MM proof record F gate <side> --gate TEXT --gate-files GLOB…` |
| `decisions.md` | the why: non-obvious choices, debates, deciders (history, not state; out of `spec_hash`; format in `CLI.md`) | composer when a worker returns and during review/rework; explore/model at the checkpoints; checked by `MM why check F/decisions.md` and `MM lint` |

## Worktrees and packs
Inside the repository, never a sibling folder: a block's worktree is `.worktrees/<feature>/<id>`
(branch `block/<id>`), the packs handed to workers are saved under `.worktrees/packs/<feature>/`
(`<id>.md`). Paths are relative to the repository root; `.worktrees/` is added to `.gitignore`
**before** the first worktree is created. Candidates stay where `compose` puts them (the
git-common-dir). Pass every path to a worker absolute.

## The tool — stateless commands
`MM` abbreviates the full command the calling prompt resolved (`python3 "@@MISMAGENT_SKILLS@@/mismagent-worker-composer/scripts/mismagent.py"`):
write that command out in every call — never a shell alias, variable or function.
The repository is the git toplevel of `F` (`diff-range`: of the working directory). A block's
branch is `block/<id>`.
- `MM status F --integration B` — read-only; lists **anomalies**: a block in `doing/`, not yet
  integrated, with no worktree; a registered worktree whose directory is gone; a leftover candidate; an `integrated/` block not an ancestor of
  the line; a `review-proof` whose `spec_hash` no longer matches; a block in `done/` that is not finishable.
  Exit 1 if any.
- `MM lint F` — exact structural checks (listed in `CLI.md`); each gap names its `bounce_to`.
  `MM lint --adrs <dir>` checks ADRs before any manifest exists.
- `MM manifest render F` — writes the block files from `building-blocks.yaml` (in place; refuses
  incomplete rows, duplicates, context changes — writing nothing).
- `MM why append F/decisions.md --entry <file>` — the recorder's only way to add decision notes.
- `MM ready F` — while a scaffold of the feature is not integrated and `done`, only the scaffold;
  then blocks in `todo/`, not parked, whose consumed boundaries' owners are `integrated/`,
  not named in an open spike's `Unblocks`; ordered by wave, release, manifest order. Plus
  `finishable`: blocks in `doing/`, integrated, whose every boundary is welded (its owner and all
  its consumers integrated).
- `MM move F <id> --to todo|doing|done` — legal moves only (`todo→doing`, `doing→todo`, `doing→done`
  only if finishable); also spike nodes. Read `ok`: a refusal is `ok:false` + `refused` (exit 1). An
  integrated owner waits in `doing/` for its consumers — normal, not unfinished work.
- `MM pack F <id>` — the worker's (and reviewers') context, headed by its `spec_hash` (the same
  dependency resolution); a pre-release group id packs its `rework/<id>-<n>.md` files.
- `MM diff-range --base B --head X` — the three-dot review range from the merge-base.
- `MM proof record F review <id> --sha S --spec-hash H` (refused unless `H`, the reviewed pack's, is
  still the current one) · `MM proof check F review <id> --sha S` · `MM proof record|check F gate <side> --gate TEXT
  --gate-files GLOB…`.
- `MM compose start F <id> --integration B --branch X` → candidate worktree = line tip + the branch;
  refuses unless a fresh review proof exists for the branch's HEAD (a `scaffold` block needs none:
  its acceptance is the gate alone), and while any candidate is open. `MM compose promote F <id>` →
  fast-forward the line only if the candidate is clean, its HEAD is the recorded merge, the line has
  not moved, and the review proof is still fresh; writes `integrated/<id>.json`. `MM compose abort F
  <id>` → removes the candidate (works even half-created), keeps `candidate/<id>` as evidence.

## The composer's procedure (one firing)
0. `move --to done` every `finishable` block of `MM ready` (exact: a crash may follow a promote),
   then `MM status` — any anomaly → **report it and ask the user; end the firing.** Never guess.
1. Readiness, every firing: `MM lint` + the judgment checks.
2. Greenfield: the scaffold first (`MM ready` offers nothing else until it is integrated and done) —
   build, gate only, `proof record gate`, compose (no review).
3. **Build:** for each block of `MM ready` up to the cap: `move --to doing`, worktree
   `.worktrees/<feature>/<id>` from the line tip (an un-parked block reuses its branch and
   worktree), dispatch the worker with `MM pack` saved under `.worktrees/packs/<feature>/`.
4. **As each worker returns:** `BOUNCED` → park (`move --to todo` + `open-questions/`).
   `BLOCKED` → report. `READY-FOR-REVIEW` → record its `DECISIONS` (`MM why append`), queue it for
   integration. An entry is `accepted` when the choice is made — integration is `integrated/`'s fact.
5. **Integrate, one at a time:** reviewers on `diff-range` + one pack → FAIL/HIGH: write
   `rework/<id>-<n+1>.md`, re-dispatch the worker on its existing worktree with it (no `ready`, no
   `move`; after cycle 2 → park) · PASS: `proof record review --spec-hash <the pack's>` →
   `compose start` → in the candidate run the gate + the contract test of every owner↔consumer pair
   whose both sides are in the candidate → green: `compose promote`, then step 0's finish ·
   red: `compose abort`, rework with the red (the reviewers say whether owner, consumer or contract).
6. Report; end. The next firing starts again from 0.

Out of this procedure, in prose: central-risk spikes (wave 0), releases and pre-release fixes (they
go through step 5 like any change: an id that is not a block — a pre-release group — has its
`rework/<id>-<n>.md` as its spec and its pack, so its review proof goes stale when those files
change), lessons harvest.
