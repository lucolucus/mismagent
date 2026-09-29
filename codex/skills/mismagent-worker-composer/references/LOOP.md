# The build loop — design (v0.25)

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
| `open-questions/<id>.md` | parked: a question for the user; `closed/` holds the answered ones (ignored by `status`/`ready`) | composer; once its answer is in `decisions.md`: `MM question close` (composer) or deleted by `build-manifest` |
| `rework/<id>-<n>.md` | the failures and HIGH findings of rework cycle n, or a red candidate / merge conflict (the cap counts these files; a group's `-1` is its spec) | `MM review ingest` · `MM rework write` |
| `review-ingest/<id>-<attempt>.json` | an ingested review attempt: its reports' hashes and result (an identical retry returns it) | `MM review ingest` |
| `review-proof/<id>.json` | reviewed `sha` + `spec_hash` | `MM review ingest` (action `promote`) · `MM proof record F review <id> --sha S --spec-hash H` |
| `integrated/<id>.json` | promoted: the block's sha is on the integration line | `MM compose promote F <id>` |
| `progress/<id>.json` | a worker's checkpoint at a green AC boundary: `head`, `spec_hash`, `attempt`, what is done, what is next | `MM progress record F <id> --head <sha> --spec-hash <h> --json <checkpoint> [--extra <path>]…`; deleted by `MM move F <id> --to done` |
| `gate-proof/<side>/proof.json` | the gate's red-green proof (project fact) | `MM proof record F gate <side> --gate TEXT --gate-files GLOB…` |
| `pre-release.md` | deferred MED/LOW findings, one line each (format in `CLI.md`); marks `[x]`/`[~]` | `MM review ingest` appends lines (idempotent); marks only by `MM release close\|waive` |
| `release-decisions/<Rn>.md` · `release-evidence/<Rn>.md` | the close/waive records (one JSON block) · the verifier's per-finding evidence | `MM release close\|waive` · composer (from the verifier's return) |
| `decisions.md` | the why: non-obvious choices, debates, deciders (history, not state; out of `spec_hash`; format in `CLI.md`) | composer after the block's promote (what review/rework produced is collected until then, never written before); new evidence later completes `Debate`/`Result` only; explore/model at the checkpoints; checked by `MM why check F/decisions.md` and `MM lint` |

## Worktrees, packs and handoffs
Inside the repository, never a sibling folder: a block's worktree is `.worktrees/<feature>/<id>`
(branch `block/<id>`), the packs handed to workers are saved under `.worktrees/packs/<feature>/`
(`<id>.md`). Handoffs are files at paths the composer designates per dispatch (ignored, never
committed), so a return stays a few lines: each reviewer writes its full report to
`.worktrees/reviews/<feature>/<id>-<attempt>-<verifier|code-review>.json` (schema in `CLI.md`); a
worker writes its decision-note entries to `.worktrees/returns/<feature>/<id>-<attempt>.md`. Paths are relative to the repository root; `.worktrees/` is added to `.gitignore`
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
  Exit 1 if any. Plus `outcome` (`done` · `work` · `idle` · `anomaly`, `CLI.md`): what a runner reads
  — a release with no blocks, or awaiting the user's confirmation, is `idle`, one with record ↔ mark gaps `work`; and `resume`: the
  blocks in `doing/` not integrated (facts about their worktrees, never "interrupted"; with a
  recorded checkpoint, its `progress` and whether it is still `fresh`).
- `MM progress record F <id> --head <sha> --spec-hash <h> --json <path|-> [--extra <path>]…` — the
  composer records a worker's `CHECKPOINT` (atomic; refused unless `<id>` is a manifest block in
  `doing/`, `--head` is `block/<id>`'s tip, its worktree clean, the spec hash current, and something
  progressed since the last record); `attempt` counts the checkpoints; the dispatch's `--extra` files
  are stored and re-packed with the checkpoint.
- `MM lint F` — exact structural checks (listed in `CLI.md`); each gap names its `bounce_to`;
  `manifest` says `legacy` (hand-written block files) or `rendered`.
  `MM lint --adrs <dir>` checks ADRs before any manifest exists.
- `MM manifest render F` — writes the block files from `building-blocks.yaml` (in place; refuses
  incomplete rows, duplicates, context changes — writing nothing).
- `MM why append F/decisions.md --entry <file>` — the recorder's only way to add decision notes
  (`MM why template F/decisions.md`: a valid skeleton; `MM why append --help`: the rules).
- `MM question close F <id> --decision D-NNNN` — an answered open question to `open-questions/closed/`.
- `MM release list|group|close|waive|confirm F <Rn> …` — the release path (`CLI.md`, Releases):
  ONE evaluation (HIGH/FAIL and MED block, a MED freed only by a verified close or a recorded
  waiver, LOW advisory); records written only by the tool, the whole batch validated first (`--replace <finding>` repairs an invalid record);
  `confirm` fast-forwards the base and tags, on the user's consent, never a push.
- `MM ready F` — while a scaffold of the feature is not integrated and `done`, only the scaffold;
  then blocks in `todo/`, not parked, whose consumed boundaries' owners and `after:` blocks are
  `integrated/`, not named (a `- <id>` line) in an open spike's `Unblocks`; ordered by wave, release, manifest order. Plus
  `finishable`: blocks in `doing/`, integrated, whose every boundary is welded (its owner and all
  its consumers integrated).
- `MM move F <id> --to todo|doing|done` — legal moves only (`todo→doing`, `doing→todo`, `doing→done`
  only if finishable); also spike nodes. Read `ok`: a refusal is `ok:false` + `refused` (exit 1). An
  integrated owner waits in `doing/` for its consumers — normal, not unfinished work.
- `MM pack F <id>` — the worker's (and reviewers') context, headed by its `spec_hash` (the same
  dependency resolution) + a fresh checkpoint first + the open `pre-release.md` lines of the block
  and its boundary neighbours as advisory notes (the rest counted in one line); a pre-release group id
  packs its `rework/<id>-<n>.md` files.
- `MM diff-range --base B --head X` — the three-dot review range from the merge-base.
- `MM review template F <id> --attempt N --reviewer verifier|code-review --sha S --spec-hash H --out <report>`
  — the report skeleton at the reviewer's path, each placeholder stating its rule.
- `MM review ingest F <id> --attempt N --depth standard|deep --file <report>… --sha S --spec-hash H` —
  validates the depth's full report set against the block, its branch tip and its current spec
  (else nothing written), files every MED/LOW deferral in `pre-release.md` (idempotent, every
  attempt), and returns ONE action: `promote` (review proof recorded) · `rework` (one
  `rework/<id>-<n>.md`) · `park` (rework cap) · `decide` (a human choice) · `blocked` (a verifier
  `SKIP`); precedence decide → blocked → rework/park → promote. A non-promote action drops the
  review proof; an identical retry returns the recorded result. `--answered D-NNNN` (recorded notes)
  re-ingests a `decide` attempt with its Decision findings answered: no new review. The composer acts on `action` and
  records the returned `objections` in the decision note — never reads the findings.
- `MM rework write F <id> --reason candidate-red|merge-conflict|other --evidence <file|->` — the
  next rework file for a red candidate or a merge conflict, same numbering and cap (`park` at the
  cap); drops the review proof.
- `MM state commit F -m <msg> --integration B` — commits exactly the changes under `<output_dir>`
  on the integration checkout (refuses another branch, an open candidate, anything else staged).
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
3. **Build:** first each `resume` block — a `result` (its worker returned, the lines at the end of
   its handoff) → step 4 with it; else its worker again on its existing worktree with a fresh pack,
   from its `progress` or its `commits`; then for each block of `MM ready` up to the cap: `move --to doing`, worktree
   `.worktrees/<feature>/<id>` from the line tip (an un-parked block reuses its branch and
   worktree), dispatch the worker with `MM pack` saved under `.worktrees/packs/<feature>/`.
   Every dispatch (worker, rework, reviewer) runs in the **foreground** — independent ones in
   parallel, in one message, where possible.
4. **As each worker returns:** `BOUNCED` → park (`move --to todo` + `open-questions/`; an answer
   that needs no code → `move --to doing`, straight to step 5 on its branch; once the answer is
   recorded, `question close`).
   `BLOCKED` → report. `READY-FOR-REVIEW` → queue it for integration with its handoff file
   (`.worktrees/returns/…`, its decision entries), which the reviewers get by path, as it is. `CHECKPOINT` (a long session, stopped at a **green** AC boundary,
   its work committed) → `MM progress record` with its head, the pack's spec hash, the checkpoint
   and the dispatch's `--extra` files, then dispatch a **fresh** worker in the same worktree with a fresh `MM pack` (it carries the
   checkpoint): a context reset, not a watchdog — one active session per block; gate, verifier and
   review still run once, at `READY-FOR-REVIEW`. Refused `no progress since attempt N` → treat it
   as `BLOCKED` (ask the user). Refused otherwise (head moved, dirty tree, spec changed) → the work is
   unverified: inspect the worktree, never record by hand. A crash before the record is the same:
   the `resume` entry shows no `progress` or a stale one (a dirty tree included): the worker
   continues from the branch's commits, re-running the tests.
5. **Integrate, one at a time:** reviewers on `diff-range` + one pack, each writing its report to
   its designated `.worktrees/reviews/…` path (pre-filled by `review template`) and returning a verdict line → `MM review ingest`
   with the depth's reports, the attempt, `head_sha` and the pack's spec hash → act on `action`:
   `rework` → re-dispatch the worker on its existing worktree with the returned `rework` file (no
   `ready`, no `move`) · `decide` / `park` → park (`move --to todo` + `open-questions/<id>.md`
   with `reason` and the report paths; answered with no code needed → ingest the same attempt
   again with `--answered`) · `blocked` → report it (a strategy problem, not the block's) ·
   `promote` (the proof is recorded) → `state commit` → `compose start` (a merge conflict → `rework write --reason merge-conflict`) → in the candidate run the
   gate + the contract test of every owner↔consumer pair whose both sides are in the candidate →
   green: `compose promote`, then `MM why append F/decisions.md --entry <file>` for each of the block's
   `.worktrees/returns/<feature>/<id>-<attempt>.md` files (every attempt's; their links now resolve
   on the line), step 0's finish, `state commit` · red: `compose abort`, then `rework write --reason candidate-red`
   with the red output (the reviewers say whether owner, consumer or contract); `park` at the cap.
   `objections` from the ingest go to the decision note's `Debate`/`Result`.
6. Report; end — once **the dispatch wave** of this firing is complete: every block dispatched in it
   integrated, parked or blocked, nothing left running, no candidate open. **One completed wave per
   firing**; the next firing starts fresh from 0 (state is on disk).

**Commits.** The composer commits `F` only with `MM state commit` — before `compose start` and after
`compose promote`, never between (a commit on the line moves it and the promote refuses); also at
the end of the firing. Never a hand `git add`/`commit` of state.

A release is a **tag on the line, never a layer in the code**: its one `composition` block
(`composition: true`, after every other block of its release and side and after the previous
release's composition block) extends the composition root
named in `architecture.md` (`composition_root:`) in place; the others publish their pieces from
their own dirs.

Out of this procedure, in the composer's prose: central-risk spikes (wave 0), lessons harvest, and
releases — their procedure lives in the composer's `Releases` section only, their exact semantics in
`CLI.md`. A pre-release group goes through step 5 like any change: its spec and ONE pack are its
`rework/<id>-<n>.md` plus the blocks it names (dependencies once), so its review proof goes stale
when any of them changes.
