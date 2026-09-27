# `mismagent.py` — the build's deterministic tool

**Stateless: it computes and refuses; it never guesses and never recovers on its own.** The design
and the composer's procedure are in `LOOP.md`; this file is the interface. Python 3 stdlib only.
`MM` is an **editorial abbreviation**, not a shell alias, variable or function: in every command
write the full command the calling prompt resolved — `python3 "<plugin root>/tools/mismagent.py"`,
the path quoted — so each Bash call stands alone (no word splitting, nothing kept between calls). `F` = `<output_dir>/features/<feature>/`
(a project root with a single feature resolves to it). **One repository per project**: the repo is the
git toplevel of `F` (for `diff-range`, of the working directory). A block's branch is `block/<id>`.
Output: JSON on stdout (`pack`: Markdown). Exit `0` ok · `1` refused / anomaly / gap (the JSON says
why) · `2` usage or input error (an unreadable manifest names its line). Tests:
`python3 -m unittest discover -s tools/tests`.

| Command | Output |
|---|---|
| `MM status F --integration B` | `{ok, anomalies:[{kind, id, detail}], outcome, work:[…], waiting:[…], resume:[{id, branch, worktree, uncommitted}]}` — exit 1 if any anomaly |
| `MM lint F` · `MM lint --adrs <dir>` | `{ok, manifest: legacy\|rendered, gaps:[{rule, where, gap, bounce_to}], deferred:[{where, file, until}]}` (`--adrs`: no `manifest`) |
| `MM why check <file>` | `{ok, file, entries, active, errors:[{id, rule, error}]}` — read-only; no manifest needed |
| `MM why append <file> --entry <entry-file>` | `{ok:true, file, appended, updated, unchanged, superseded}` or `{ok:false, refused[, errors]}` |
| `MM manifest render F` | `{ok:true, written, unchanged, orphans}` or `{ok:false, refused, problems:[{id, problem}]}` |
| `MM ready F` | `{ready:[{id, type, wave, release}], excluded:[{id, reason}], finishable:[id], open_spikes:[{id, state, central, unblocks}], resume:[…]}` |
| `MM move F <id> --to todo\|doing\|done` | `{ok:true, id, from, to, path, git}` or `{ok:false, id, from, refused}` (no `to`: nothing moved) |
| `MM pack F <id> --extra FILE…` | Markdown headed `spec_hash: <h>`; every section carries its `source:` path |
| `MM diff-range --base B --head X` | `{base_sha, head_sha, merge_base, range, files:[{status, path}]}` |
| `MM proof record F review <id> --sha S --spec-hash H` · `MM proof check F review <id> --sha S` | `{recorded, sha}` or `{refused, reviewed, current}` · `{fresh, stale_because}` |
| `MM proof record F gate <side> --gate TEXT --gate-files GLOB…` · `MM proof check F gate <side> --gate TEXT --gate-files GLOB…` | `{recorded, proof[, warnings]}` · `{fresh, stale_because, proof}` |
| `MM compose start F <id> --integration B --branch X` | `{candidate_path, candidate_sha, base_sha, branch_sha}` or `{refused}` |
| `MM compose promote F <id>` · `MM compose abort F <id>` | `{promoted, integration_sha}` · `{aborted, kept_branch}` |
| `MM release list F <Rn> --integration B` | `{release, sha, blocks:[{id, state, integrated}], blocking, advisory, waived, closed, waiting, errors, gaps, releasable, confirmed}` — read-only |
| `MM release close F <Rn> --entries <json> [--replace <finding>…]` · `MM release waive F <Rn> --entries <json> [--replace <finding>…]` | `{ok:true, release, action, lines, findings, replaced, file}` or `{ok:false, refused, problems}` |
| `MM release group F <Rn> --id pre-<Rn>-<k> --lines <line>:<finding>…` | `{ok:true, id, file, blocks, findings, context, unchanged}` or `{ok:false, refused, problems}` |
| `MM release confirm F <Rn> --integration B --sha S --tag TAG --merge-to BASE --base-sha T --by <user> --consent <ref>` | `{ok:true, confirmed, release, sha, tag, merge_to, base_sha_before, partial, unchanged}` or `{ok:false, refused, problems}` |

## Exact semantics

- **integrated** = `F/integrated/<id>.json` exists (written only by `compose promote`: `{sha` = the
  block branch's reviewed head, `merge` = the promoted candidate, `integration}`). A boundary is
  **welded** when its owner and every consumer are integrated. A block is **finishable** when it is
  integrated and every boundary it touches (consumed, owned, or listed as consumer) is welded.
- **status** anomalies: `doing_without_worktree` (in `doing/`, not integrated, no worktree on
  `block/<id>` — a worktree whose directory is gone does not count; a `central` spike node in `doing/`
  with neither `F/spikes/<id>.md` nor a worktree on `spike/<id>`) · `missing_worktree` (a
  registered worktree whose directory is gone; `id` = its branch) · `leftover_candidate` (any candidate metadata, half-written metadata, candidate
  directory or `candidate/*` worktree — a kept `candidate/<id>` branch alone is evidence, not an
  anomaly) · `integrated_not_on_line` (the recorded `sha` is not an ancestor of `B`) ·
  `stale_review_proof` (its `spec_hash` differs from the current one) · `done_unwelded` (in `done/`,
  not finishable) · `lint_gap` (checked only before `done`/`idle`: a `lint` gap of rule `ids.*`,
  `consumes.boundary`, `boundary.owner`, `after.*`, `blockfile.exists|unique|orphan`, `spikes.*` —
  `id` = the rule). Read-only. **outcome** (for a runner; computed with `ready`'s rules and the ONE
  release evaluation below): `anomaly`
  (any of the above) · `work` — something to do now (`work` lists it): a `ready` or `finishable`
  block, a `resume` block, a `central` spike in `backlog/`/`todo/`, or in `doing/` with its worktree but no evidence yet, a cleanup node
  in `todo/`/`doing/`, a release whose blocks are all done and integrated with a blocking line, a release
  with record ↔ mark `gaps` (whatever its blocks' state: the composer repairs them) ·
  `idle` — only work waiting on a decision or an external condition (`waiting` lists it: parked
  blocks and what they hold up, an open question, a spike not yet closed — a `central` one only once its evidence exists —, a cleanup's `ready_when`,
  a release with no blocks (its lines wait), a releasable release awaiting the user's `release confirm`)
  · `done` — every block in `done/`, every release confirmed, no spike/cleanup node outside
  `done/`, no open question (open LOW lines never prevent it). `ready: []` alone is never `idle`.
- **resume** (`status` and `ready`) = each block in `doing/` not integrated, with its branch, its
  worktree (null if none) and the count of uncommitted changes there: facts, never a diagnosis — a
  dirty tree with no commit also describes a worker still running.
- **ready** = in `todo/`, in the manifest, no `F/open-questions/<id>.md`; while a `scaffold` block of
  the feature is not both integrated and in `done/`, only scaffolds (the open spikes stay listed); not named in the
  `## Unblocks` of a spike node (`tasks/<side>/<state>/<id>.md`, `type: spike`) that is not `done` —
  only full `- <block-id>` lines count, prose is ignored —, every consumed boundary's owner and every
  `after:` block **integrated** (not necessarily `done`). Order: `wave`, then release (the `releases:` keys in
  order, then undeclared labels in natural order), then manifest order. The cap is the composer's.
- **move**: blocks `todo→doing`, `doing→todo`, `doing→done` (only if finishable); spike/cleanup
  nodes `backlog|todo→doing`, `doing→done`. Nothing else. A tracked file moves with `git mv`. A
  refusal is `ok:false` + `refused`, exit 1, no `to`, filesystem untouched. An integrated block not
  yet finishable stays in `doing/` (the board badges it "integrated, closing pending").
- **manifest render** writes every block file from its row: frontmatter = the row minus `what`,
  `sources`, `tests_nl`, `notes`; body = `## What to do` (`what`), `## Invariants` (the row's),
  `## Tasks` (`tests_nl`), `## Dependencies` (each touched boundary: role, consumers,
  `contract_test`, pinned types and keys inlined), `## Notes`, `Sources:` (`sources`). A block keeps
  its state folder (a new one lands in `todo/`); an identical file is not rewritten. Refuses,
  writing nothing, on: a non-scaffold row missing `what`, `sources` or `tests_nl` (blank = missing),
  an empty criterion, a touched boundary whose `pinned_types`/`keys` is not a mapping, an `INV-n`
  or command not covered by `tests_nl`; a duplicate id or file, a file under another context (a move
  is yours). Files without a row are listed as `orphans`, untouched. It writes documents only: the
  decisions and criteria are the row's.
- **why append** adds the entry file's `### D-NNNN` entries (their ids as written, nothing assigned)
  only if the whole file then passes `why check` and — when the file sits beside a manifest — each
  added or updated entry's scope names a row or release of it (else `meta.scope`, nothing written;
  a wrong scope already in history is fixed by a new entry that `Supersedes` it, never by an edit);
  an identical entry already present is a no-op. The
  same id with other content is an **update**, replaced in place, only when it changes nothing but
  `Debate`/`Result` and adds an `ADR:` backlink (an existing one kept); anything else is refused. An
  entry that `Supersedes` an accepted one flips its `status` to `superseded`. Refused → nothing written.
- **pack** / **spec_hash** share ONE dependency resolution: the block file, its manifest row, the rows
  of the boundaries it touches, and the ADRs of the block ∪ of the owners of the boundaries it
  consumes (`<output_dir>/decisions/NNNN-*.md`) ∪ every ADR with a check whose `from` is the block; a `scaffold` block honours every block's ADRs (it
  writes the checks with no `from`). The pack adds the goal (`F/product-brief.md`), the
  ADRs' `## Decision` + `## Rationale` (else `## Consequences`) and their `enforced_by` checks, each
  marked `applicable` (no `from`, or `from` integrated), `THIS block writes it` (`from` = the packed
  block), `not yet applicable` or `UNRESOLVED` (no such block). `from` resolves **project-wide**:
  integrated = any feature's `integrated/<from>.json` or `blocks/*/done/<from>.md`; an entry that is not `{check: <repo-relative path>, from: <block>}`
  is listed `LEGACY` (never executed). Then the block type's `## <type>` section of
  `<output_dir>/architetture/lessons-by-block-type.md` (struck `~~…~~` lessons skipped), and each
  active decision notes (below), and each
  **open finding** of `F/pre-release.md` (each `- [ ]` line with its line number; `[x]` fixed and
  `[~]` waived left out; advisory, a block's pack only), and each
  `--extra` file, under a first line `spec_hash: <h>`. `spec_hash` hashes the block file's **content** (not its folder), so a state move
  never makes a proof stale; `after:` is build order, not spec: out of the row's hash and of the rendered file. An id that is not a block (a pre-release group) has its
  `F/rework/<id>-*.md` files as its spec plus — when `<id>-1.md` has `blocks:` frontmatter (`release group`) —
  those blocks' files and rows and the boundaries and ADRs they resolve, **each once**; its ONE pack
  is the rework files, those blocks, boundaries, ADRs and types' lessons (each once), and the notes
  scoped `release:<Rn>` or to those blocks. A group without frontmatter (legacy) is its rework files alone.
- **diff-range**: `range` = `<merge_base>..<head_sha>` (≡ `B...X`): files the line gained after the
  branch was cut never show as deleted by the block.
- **review proof** `F/review-proof/<id>.json` = `{sha, spec_hash}`. `record` refuses unless
  `--spec-hash` (the reviewed pack's) is the current one: no proof for a spec nobody reviewed. Fresh ⇔ it exists, its `sha` is
  `--sha` resolved, and its `spec_hash` is the current one.
- **gate proof** `F/gate-proof/<side>/proof.json` = `{gate, gate_files, gate_hash}`; `gate_hash` =
  the gate string + each glob + the content of every file it matches (globs relative to the repo,
  `**` allowed). `record` refuses a glob that matches no file, and **warns** (`warnings`) on matches
  that look generated (git-ignored, under a build/cache directory, compiled/log files) — still
  hashed: `gate_files` name stable inputs, fix the globs. Fresh ⇔ **any**
  `<output_dir>/features/*/gate-proof/<side>/proof.json` has the current `gate_hash` (a project
  fact); it goes stale only when the gate string, the glob list or a matched file changes.
- **compose** keeps its metadata in `<git-common-dir>/mismagent-candidates/<id>.json`, written
  atomically (tmp + rename) **before** the worktree exists. `start` refuses while any candidate is
  open, and without a fresh review proof for `X`'s HEAD (a `scaffold` block needs none); it cuts
  `candidate/<id>` from `B`'s tip and merges `X` `--no-ff` (a conflict refuses and cleans up).
  `promote` refuses unless: the metadata says `open`, `B` has not moved since `start`, the candidate
  worktree has no uncommitted or untracked change, its HEAD is the recorded merge, and the review
  proof is still fresh for the recorded branch sha. Then it fast-forwards `B` (compare-and-swap on the
  ref; if `B` is checked out, `merge --ff-only` there, which git refuses if it would overwrite local
  changes), writes `F/integrated/<id>.json`, removes the candidate worktree and branch. `abort`
  removes whatever exists of the candidate (worktree, directory, metadata) — also a half-created one
  — and keeps `candidate/<id>` as evidence. No revert, no timeout. Candidates live in the
  git-common-dir; block worktrees and packs do not (`LOOP.md`, Worktrees).

## Releases — `F/pre-release.md`, records, confirm

**Line** (one per deferred finding): `- [ ] <release> · <id> · <sev> · <locator> · <issue> · <reviewer> · <date>`;
`<sev>` ∈ `HIGH | FAIL | MED | LOW`; `<locator>` = `file:line[-line]` or `path#symbol` (a symbol does not
rot). Marks: `[ ]` open · `[x]` closed · `[~]` waived — flipped only by `release close|waive`; text
after the seventh field is an annotation. **Identity** = a hash of the seven fields (`finding`, 12
hex), never the mark, the line number or an annotation: the line number only **selects**, and every
command takes both (a line that is now another finding is refused — re-read `release list`).

**Evaluation** (ONE function: `status`, `release list`, `release confirm`) of Rn on `B`'s tip:
`blocking` = each Rn line that is open HIGH/FAIL/MED, malformed, a HIGH/FAIL marked `[~]`, or marked
without a valid last record · a close record holds while its `sha` is on `B`, its evidence names the
finding, and the locator's file is unchanged between that `sha` and `B` (a records-only commit
stales nothing; a code change asks for a new verification) · `advisory` = the open LOW lines of Rn
and of every earlier release (a **view** with their `release`; never copied, never work) · `waived` /
`closed` = lines freed by a valid record · `waiting` = Rn has no blocks, or a block not done and
integrated (its `integrated/` record's `sha` a commit on `B`) · `gaps` = Rn's `release.*` lint gaps
(records ↔ marks) · `releasable` ⇔ blocks non-empty ∧ none waiting ∧ nothing blocking ∧ readable
records ∧ no gaps ·
`confirmed` = a `release confirm` tag of Rn whose commit is on its merge-to branch.

**close / waive** `--entries` = a JSON array (inline or a file). close: `{line, finding, sha, by,
evidence}` — `sha` a commit (stored resolved), `evidence` = `release-evidence/<Rn>.md[#anchor]`, a
file that names the finding (per finding: sha, current location, the verification run, its result).
waive: `{line, finding, by, consent, reason, risk, revisit}` — `by` the deciding user, `consent` a
reference to the message; a HIGH/FAIL is never waived, a closed line neither. Exactly these keys,
non-empty. The **whole batch** is validated first (keys, selector, release, duplicates, sha,
evidence); any problem → nothing written. Then the records are appended — `action` and `at` set by
the tool — to the ONE ```json block `{"records": [...]}` of `F/release-decisions/<Rn>.md` (prose
around it, e.g. a legacy file, kept), and the marks flip. The last record of a finding is its
current one (a re-verification appends). An invalid record already in the file is refused (nothing
written) unless its finding is in `--replace`: each `--replace` finding (one of the batch) has its
earlier records, valid or not, dropped before the new one is appended — the repair path.

**group** writes `F/rework/<id>-1.md` (`<id>` = `pre-<Rn>-<k>`): frontmatter `release`, `blocks`,
`findings` (the hashes), then the selected lines copied. `--lines` takes `<line>:<finding>` pairs
(from `release list`). Refused: a line that is now another finding, a line not open or not of Rn, a
block not in the manifest, lines across contexts (or `side:` values), a finding already in another
group, an existing file with other content (an identical one: `unchanged`).

**confirm** — preflight, all of it, nothing written on any failure: `S` is `B`'s tip; Rn releasable
and its `release.*` lint clean; the checkout of `F` is on `B` and clean; `BASE`'s checkout (if any)
clean; `BASE` at `T` with `T` an ancestor of `S` (else diverged: stop, never a new merge) — or already
at `S`; `TAG` a valid tag name (`git check-ref-format`), absent or already THIS confirmation's tag —
same release, `S`, `BASE`, `T`, `B`, `--by`, `--consent` (else collision); `--by`, `--consent`
non-empty. Then `BASE` is fast-forwarded to `S` (compare-and-swap; `merge --ff-only` in its checkout)
and an annotated `TAG` is put on `S`, its message carrying `mismagent-release: <feature>/<Rn>`,
`integration: B @ S`, `merge-to: BASE (from T)`, `decided:`, `consent:`. An identical repeat is
`unchanged`; a half-done one (merge or tag already there) is completed and named in `partial`. Never
a push. Tag + ancestry are the confirmation: no flag is written.

## lint — the exact checks (nothing else)
Each gap names its `bounce_to` (`build-manifest` unless noted).

| rule | check |
|---|---|
| `ids.present` · `ids.unique` | every block/boundary row has an id; ids unique per kind |
| `type.valid` | block `type` ∈ aggregate, application-service, port, adapter, read-model, ui, scaffold |
| `wave.valid` · `wave.scaffold` | `wave` a non-negative integer; `0` iff `type: scaffold` |
| `wave.owner_first` | a consumed boundary's owner has a lower `wave` than the consumer |
| `consumes.boundary` | every `consumes` entry is a boundary id |
| `boundary.owner` · `boundary.consumers` | `owner` / each consumer is a block id; `consumers` and the blocks' `consumes` agree both ways |
| `release.required` · `release.declared` | every non-scaffold block has `release:`; declared in `releases:` when that section exists |
| `scaffold.domain_free` | a `scaffold` row has no `invariants`, `invariant_fields`, `commands`, `consumes`, `pinned_types`, `view_shape`, `keys`, and owns no boundary |
| `boundary.pinned_types` | `pinned_types` present and non-empty; `pinned_types`/`keys` each a mapping `{name: text}` (never coerced) → `architect` |
| `boundary.contract_test` | `invariant-test \| consumer-driven` |
| `blockfile.exists` · `blockfile.unique` · `blockfile.orphan` | exactly one `blocks/<ctx>/{todo,doing,done}/<id>.md` per row; no file without a row |
| `blockfile.frontmatter` · `blockfile.context_dir` | frontmatter `type`/`context`/`wave` equal the row; the file sits under `blocks/<context>/` |
| `blockfile.status_free` | no `status:` field, no checkbox |
| `spec.what` · `spec.tasks` · `spec.sources` | non-scaffold: `## What to do` non-empty; `## Tasks` ≥ 1 list item; a non-empty `Sources:` line |
| `spec.invariants` | each `INV-n` of the row's `invariants` is named in `## Tasks`, matched by number: `INV[-_ ]?n` (case-insensitive; `INV-1` ≠ `INV-12`), so `test_INV_12_…` counts; with untagged invariants, criteria ≥ invariants |
| `spec.commands` | each `commands` entry appears in `## Tasks` |
| `adr.checks` | every `enforced_by` entry of the ADRs the blocks resolve (as `pack`) is `{check: <repo-relative path>, from: <block>?}`, its `from` is a block of some feature's manifest, and the check exists in the repo → `architect`. A missing check is `deferred` while its `from` block is not integrated (project-wide), or — with no `from` — while a `scaffold` block is not in `done/` |
| `render.input` · `blockfile.render` | `manifest: rendered` (some row has `what:`), for every row: its render inputs are complete and its file equals `manifest render`'s output. `legacy` (no row has `what:`): hand-written files, no render check — never forced to render |
| `after.block` · `after.cycle` | `after` is a list of other block ids; no cycle in the "waits for" graph (`after` ∪ the owners of consumed boundaries) |
| `manifest.build_order` | no `build_order:` (read by nothing; order with `after:`) |
| `why.<rule>` · `why.scope` | when `F/decisions.md` exists: every `why check` error, and each active entry's `block:`/`boundary:`/`release:` scope names a row / a release of the manifest → `recorder` (who wrote the entry) |
| `release.finding` | every `- [ ]` line of `pre-release.md` has the seven fields, a severity, a locator → `composer` |
| `release.record` · `release.unverified` · `release.record_orphan` | `release-decisions/<Rn>.md` holds at most one readable ```json block of valid records; every `[x]`/`[~]` line's last record is a `close`/`waive` (a legacy mark with none: kept, flagged unverified); every record names a line of its release carrying its mark → `composer` |
| `spikes.central_node` · `spikes.central_flag` | each open `[ ]` entry of the context map's `## Open spikes` with `owner: <this feature>` and `central: true` has a `type: spike` node carrying `central: true` |

`MM lint --adrs <dir>` (before any manifest; → `architect`): `adr.filename` (`NNNN-<slug>.md`),
`adr.frontmatter` (parses; `scope`; `status` proposed|accepted|superseded), `adr.checks` (the
`enforced_by` shape); each check's `from` and existence are listed as `deferred` to `MM lint F`.

Not linted (judgment — the composer's readiness and the reviewers): whether a criterion is
meaningful, whether pinned types are complete, the gate's discrimination, whether an ADR check is
registered in the gate and discriminates (the verifier), the profile's bindings.

## Decision notes — `F/decisions.md`

The **why** of the feature: one entry per **non-obvious** choice (not per commit, finding or block),
kept as the project's history. Not a gate, not state: `spec_hash` never reads it; a rule that must bind
lives in the spec, manifest or an ADR. `F/decisions.md` is optional until a first such choice.

**Who writes.** The **recorder** writes the entry when the choice is made — a writer never becomes
the decider by writing. Build: during review/rework the composer only **collects** a worker's `DECISIONS`, the reviewers'
objections and the rework's evidence; it **records** them once the block is promoted (its links then
resolve on the line), `Debate`/`Result` already filled from what it collected. Explore/model: the conductor records the
challenger's debate and the user's choice at each checkpoint (`KILL`/`RESHAPE` included);
`build-manifest` records an open question's answer before deleting `open-questions/<id>.md`.
Reviewers and the challenger stay read-only: they cite `D-NNNN` in their `NOTES`. The recorder
writes each returned entry to a file and adds it with `MM why append F/decisions.md --entry <file>`
(never a hand edit of the file); an allowed edit below is the same command with the whole updated
entry under its own id.

**Rules.** Ids `D-0001`… per feature, appended in order; a resumed return adds no duplicate. After
it is appended (build: after the promote; explore/model: at the checkpoint), new evidence on the same
choice — a later rework, a pre-release fix — only completes its `Debate`/`Result` (same command, same
id). Exactly two other edits are allowed:
`status: accepted` → `superseded` (when a **new** entry `Supersedes` it — a changed choice is always
a new entry) and adding the `ADR:` backlink when the architect promotes it. Nothing else is edited. Nothing invented to fill a field:
an incomplete choice stays an open question. Humans are named as declared in the session — never
inferred from git (the profile's optional `people:` is an address book, not proof of approval); ask
at the checkpoint if unknown. Agents: role + block (or attempt) + tier/model when known. A choice
that changes structure, a contract, an invariant, a cross-cutting quality or is costly to reverse
→ the **architect** promotes it to an ADR (`ADR:` link; the ADR cites `<feature> D-NNNN`). Features
are archived, never deleted: so is this file. Out: transcripts, reasoning, attempt history, test
dumps, ordinary findings, backlog, open questions, progress, approvals.

**Format** — one physical line per field, ≤220 words per entry (URLs excluded), title ≤8 words:
| field | required content (word cap) |
|---|---|
| `Meta` | `<ISO date>; scope: feature\|block:<id>\|boundary:<id>\|release:<Rn>; status: accepted\|superseded[; sha: <commit>]` — sha when the choice concerns reviewed code; `release:<Rn>` for a pre-release change |
| `Question` | the problem and its decisive constraint (25) |
| `Options` | 2–3 real alternatives and why each loses (40) |
| `Hypothesis` | a testable prediction, stated before the check (25) — or, with `Check` and `Result`, the short form below |
| `Check` | method, conditions, success criterion (30) |
| `Result` | observation + a link to the evidence, or `untested`/`inconclusive` — <reason> (30) |
| `Debate` | who argued what, the objection, the outcome; `none` (40) |
| `Decision` | the choice, why, the **cost accepted** (35) |
| `By` | `decided: <who>; recorded: <who>[; consulted: <who>]` |
| `Docs` | 1–3 links (internal files, ADRs and tests count) |
| `Revisit` | the observation that reopens it (20) |
| `Confidence` · `Supersedes` · `ADR` | optional: `low\|medium\|high — <why>`, the why required (12) · the replaced `D-NNNN` · the ADR link (omit the field when none) |

**Short form** — a choice the requirements, a scope cut or an ADR already decided: `Hypothesis`,
`Check` and `Result` are **all three** `n/a — decided by <reference>`, the reference verifiable (an id
such as `REQ-3`/`ADR-0002`, or a link to the scope cut); never mixed with experiment fields. A choice
fully prescribed needs no entry at all; never invent alternatives to fill `Options`.

**Checked by `why check`** (exit 1, each error an `{id, rule}`; `MM lint` → `why.<rule>` → the
recorder): heading `### D-NNNN · <title>` at column 0 (an indented or other-level `D-NNNN` heading,
or a field line outside an entry, is an error, never skipped); known fields, one line each, none
empty or missing; word caps; ids unique and ascending; `Meta` date, scope, status, keys; `Result`
has a link unless `untested`/`inconclusive` with a reason or in the short form (all three, a
reference each); `By` has non-empty `decided:` and
`recorded:`; `Docs` 1–3 links; `Confidence` level + reason; `ADR` is a link; local links exist;
`Supersedes`/`superseded` pair up. **Judged by humans and reviewers** (never by the tool): whether
the options are real, the hypothesis testable and stated first, the check discriminating, the
evidence supports the result, the cost accepted honest, and the choice non-obvious enough to record.

A green gate or a review supports a hypothesis; it does not prove the choice was the better one.
`MM pack` carries, per block, `ID + Decision + Revisit + link` (`decisions.md#<GitHub anchor of the
full heading>`, e.g. `#d-0007--standard-csv-parser`) of the accepted entries scoped to the
feature, the block, the owners of the boundaries it consumes and the boundaries it touches — no
transitive ones (more via `--extra`). Example (fictional):
```markdown
### D-0007 · Standard CSV parser
- Meta: 2026-09-24; scope: block:import-csv; status: accepted; sha: a13b9c2
- Question: How to read CSV fields that contain separators and line breaks?
- Options: A split, fails on quoted fields; B standard parser; C extra library, unneeded features.
- Hypothesis: The standard parser reads every required format without a new dependency.
- Check: Run the agreed corpus, 24 fixtures incl. quoted separators and multiline fields; success = 24 exact matches.
- Result: A 18/24; B 24/24; [CI run](https://ci.example.com/run/412).
- Debate: worker/import-csv proposed B; code-review/import-csv objected on multiline; fixtures added, resolved.
- Decision: B, it covers the agreed corpus; we accept supporting only the agreed dialect.
- By: decided: mismagent-worker/import-csv (standard); recorded: worker-composer; consulted: Ada Example
- Docs: [RFC 4180](https://www.rfc-editor.org/rfc/rfc4180)
- Revisit: A valid product file the parser cannot read.
- Confidence: medium — the corpus is representative, not exhaustive.
```
