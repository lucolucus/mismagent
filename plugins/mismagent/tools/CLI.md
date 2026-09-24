# `mismagent.py` — the build's deterministic tool

**Stateless: it computes and refuses; it never guesses and never recovers on its own.** The design
and the composer's procedure are in `LOOP.md`; this file is the interface. Python 3 stdlib only.
`MM` = `python3 "$CLAUDE_PLUGIN_ROOT/tools/mismagent.py"`. `F` = `<output_dir>/features/<feature>/`
(a project root with a single feature resolves to it). **One repository per project**: the repo is the
git toplevel of `F` (for `diff-range`, of the working directory). A block's branch is `block/<id>`.
Output: JSON on stdout (`pack`: Markdown). Exit `0` ok · `1` refused / anomaly / gap (the JSON says
why) · `2` usage or input error (an unreadable manifest names its line). Tests:
`python3 -m unittest discover -s tools/tests`.

| Command | Output |
|---|---|
| `MM status F --integration B` | `{ok, anomalies:[{kind, id, detail}]}` — exit 1 if any |
| `MM lint F` | `{ok, gaps:[{rule, where, gap, bounce_to}], deferred:[{where, file, until}]}` |
| `MM why check <file>` | `{ok, file, entries, active, errors:[{id, rule, error}]}` — read-only; no manifest needed |
| `MM ready F` | `{ready:[{id, type, wave, release}], excluded:[{id, reason}], finishable:[id], open_spikes:[{id, state, central, unblocks}]}` |
| `MM move F <id> --to todo\|doing\|done` | `{id, from, to, path, git}` or `{refused}` |
| `MM pack F <id> --extra FILE…` | Markdown headed `spec_hash: <h>`; every section carries its `source:` path |
| `MM diff-range --base B --head X` | `{base_sha, head_sha, merge_base, range, files:[{status, path}]}` |
| `MM proof record F review <id> --sha S --spec-hash H` · `MM proof check F review <id> --sha S` | `{recorded, sha}` or `{refused, reviewed, current}` · `{fresh, stale_because}` |
| `MM proof record F gate <side> --gate TEXT --gate-files GLOB…` · `MM proof check F gate <side> --gate TEXT --gate-files GLOB…` | `{recorded, proof}` · `{fresh, stale_because, proof}` |
| `MM compose start F <id> --integration B --branch X` | `{candidate_path, candidate_sha, base_sha, branch_sha}` or `{refused}` |
| `MM compose promote F <id>` · `MM compose abort F <id>` | `{promoted, integration_sha}` · `{aborted, kept_branch}` |

## Exact semantics

- **integrated** = `F/integrated/<id>.json` exists (written only by `compose promote`: `{sha` = the
  block branch's reviewed head, `merge` = the promoted candidate, `integration}`). A boundary is
  **welded** when its owner and every consumer are integrated. A block is **finishable** when it is
  integrated and every boundary it touches (consumed, owned, or listed as consumer) is welded.
- **status** anomalies: `doing_without_worktree` (in `doing/`, not integrated, no worktree on
  `block/<id>` — a worktree whose directory is gone does not count) · `missing_worktree` (a
  registered worktree whose directory is gone; `id` = its branch) · `leftover_candidate` (any candidate metadata, half-written metadata, candidate
  directory or `candidate/*` worktree — a kept `candidate/<id>` branch alone is evidence, not an
  anomaly) · `integrated_not_on_line` (the recorded `sha` is not an ancestor of `B`) ·
  `stale_review_proof` (its `spec_hash` differs from the current one) · `done_unwelded` (in `done/`,
  not finishable). Read-only.
- **ready** = in `todo/`, in the manifest, no `F/open-questions/<id>.md`, not named in the
  `## Unblocks` of a spike node (`tasks/<side>/<state>/<id>.md`, `type: spike`) that is not `done`,
  every consumed boundary's owner integrated. Order: `wave`, then release (the `releases:` keys in
  order, then undeclared labels in natural order), then manifest order. The cap is the composer's.
- **move**: blocks `todo→doing`, `doing→todo`, `doing→done` (only if finishable); spike/cleanup
  nodes `backlog|todo→doing`, `doing→done`. Nothing else. A tracked file moves with `git mv`.
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
  `--extra` file, under a first line `spec_hash: <h>`. `spec_hash` hashes the block file's **content** (not its folder), so a state move
  never makes a proof stale. An id that is not a block (a pre-release group) has its
  `F/rework/<id>-*.md` files as its spec, and its pack is those files.
- **diff-range**: `range` = `<merge_base>..<head_sha>` (≡ `B...X`): files the line gained after the
  branch was cut never show as deleted by the block.
- **review proof** `F/review-proof/<id>.json` = `{sha, spec_hash}`. `record` refuses unless
  `--spec-hash` (the reviewed pack's) is the current one: no proof for a spec nobody reviewed. Fresh ⇔ it exists, its `sha` is
  `--sha` resolved, and its `spec_hash` is the current one.
- **gate proof** `F/gate-proof/<side>/proof.json` = `{gate, gate_files, gate_hash}`; `gate_hash` =
  the gate string + each glob + the content of every file it matches (globs relative to the repo,
  `**` allowed). `record` refuses a glob that matches no file. Fresh ⇔ **any**
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
  — and keeps `candidate/<id>` as evidence. No revert, no timeout.

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
| `release.r0_waves` | an `R0` block's `wave` is among the first 3 distinct non-scaffold waves |
| `boundary.pinned_types` | `pinned_types` present and non-empty → `architect` |
| `boundary.contract_test` | `invariant-test \| consumer-driven` |
| `blockfile.exists` · `blockfile.unique` · `blockfile.orphan` | exactly one `blocks/<ctx>/{todo,doing,done}/<id>.md` per row; no file without a row |
| `blockfile.frontmatter` · `blockfile.context_dir` | frontmatter `type`/`context`/`wave` equal the row; the file sits under `blocks/<context>/` |
| `blockfile.status_free` | no `status:` field, no checkbox |
| `spec.what` · `spec.tasks` · `spec.sources` | non-scaffold: `## What to do` non-empty; `## Tasks` ≥ 1 list item; a `Sources:` line |
| `spec.invariants` | each `INV-n` tag of the row's `invariants` appears in `## Tasks`; with untagged invariants, criteria ≥ invariants |
| `spec.commands` | each `commands` entry appears in `## Tasks` |
| `adr.checks` | every `enforced_by` entry of the ADRs the blocks resolve (as `pack`) is `{check: <repo-relative path>, from: <block>?}`, its `from` is a block of some feature's manifest, and the check exists in the repo → `architect`. A missing check is `deferred` while its `from` block is not integrated (project-wide), or — with no `from` — while a `scaffold` block is not in `done/` |
| `why.<rule>` · `why.scope` | when `F/decisions.md` exists: every `why check` error, and each active entry's `block:`/`boundary:` scope names a row of the manifest → `recorder` (who wrote the entry) |
| `spikes.central_node` · `spikes.central_flag` | each open `[ ]` entry of the context map's `## Open spikes` with `owner: <this feature>` and `central: true` has a `type: spike` node carrying `central: true` |

Not linted (judgment — the composer's readiness and the reviewers): whether a criterion is
meaningful, whether pinned types are complete, the gate's discrimination, whether an ADR check is
registered in the gate and discriminates (the verifier), the profile's bindings.

## Decision notes — `F/decisions.md`

The **why** of the feature: one entry per **non-obvious** choice (not per commit, finding or block),
kept as the project's history. Not a gate, not state: `spec_hash` never reads it; a rule that must bind
lives in the spec, manifest or an ADR. `F/decisions.md` is optional until a first such choice.

**Who writes.** The **recorder** writes the entry when the choice is made — a writer never becomes
the decider by writing. Build: the composer records a worker's `DECISIONS` on its return and
completes `Debate`/`Result` during review/rework. Explore/model: the conductor records the
challenger's debate and the user's choice at each checkpoint (`KILL`/`RESHAPE` included);
`build-manifest` records an open question's answer before deleting `open-questions/<id>.md`.
Reviewers and the challenger stay read-only: they cite `D-NNNN` in their `NOTES`.

**Rules.** Ids `D-0001`… per feature, appended in order; a resumed return adds no duplicate. Once its
block is integrated or its checkpoint closed an entry is closed. Exactly two edits are then allowed:
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
| `Meta` | `<ISO date>; scope: feature\|block:<id>\|boundary:<id>; status: accepted\|superseded[; sha: <commit>]` — sha when the choice concerns reviewed code |
| `Question` | the problem and its decisive constraint (25) |
| `Options` | 2–3 real alternatives and why each loses (40) |
| `Hypothesis` | a testable prediction, stated before the check (25) |
| `Check` | method, conditions, success criterion (30) |
| `Result` | observation + a link to the evidence, or `untested`/`inconclusive` — <reason> (30) |
| `Debate` | who argued what, the objection, the outcome; `none` (40) |
| `Decision` | the choice, why, the **cost accepted** (35) |
| `By` | `decided: <who>; recorded: <who>[; consulted: <who>]` |
| `Docs` | 1–3 links (internal files, ADRs and tests count) |
| `Revisit` | the observation that reopens it (20) |
| `Confidence` · `Supersedes` · `ADR` | optional: `low\|medium\|high — <why>`, the why required (12) · the replaced `D-NNNN` · the ADR link (omit the field when none) |

**Checked by `why check`** (exit 1, each error an `{id, rule}`; `MM lint` → `why.<rule>` → the
recorder): heading `### D-NNNN · <title>` at column 0 (an indented or other-level `D-NNNN` heading,
or a field line outside an entry, is an error, never skipped); known fields, one line each, none
empty or missing; word caps; ids unique and ascending; `Meta` date, scope, status, keys; `Result`
has a link unless `untested`/`inconclusive` with a reason; `By` has non-empty `decided:` and
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
