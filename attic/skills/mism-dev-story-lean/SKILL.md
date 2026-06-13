---
name: mism-dev-story-lean
description: 'LEAN implementation engine of the mismAgent flow (build movement). Implements ONE lean task (Gherkin ACs + contract_ref + references) in red-green-refactor WITHOUT writing state into the file (no Status/File List/Change Log/Dev Agent Record): state = the folder. Completion gate = tests+contract-tests green, not "Status set to review". Emits the strict return. Use this skill when implementing a mismAgent task. Do not use an engine that forces writing state into the file: in mismAgent the state IS the folder, only the orchestrator moves it.'
---

# Dev Story Lean — mismAgent engine

**Goal:** implement ONE lean task until tests are green, in a single side, without
touching the state. Orientation: `methodology/mismagent.md`.

**Role:** developer. You communicate in Italian; technical names in English.

## Difference from the heavy engine (why this exists)

**Do not use an engine that forces writing state** into the file (`## Status`, `File List`,
`Change Log`, `Dev Agent Record`) and setting the Status to `review` as the completion
gate. In mismAgent **the state IS the folder** (`backlog/ todo/ doing/ done/`) and **only
the orchestrator** moves it via `git mv`. Therefore those writes are **FORBIDDEN** here
(invariant no. 1). The permanent journal is the `git log`.

## Input you receive

- **absolute** path of the lean task-file (frontmatter `id/side/repo/slice/depends_on/contract_ref/references`);
- **working dir**: absolute path of the sub-repo (or of a dedicated git worktree if you run in parallel on the same side);
- name of the **story branch** (where you commit) and of the **base/epic branch**;
- (rework) the verifier/review findings to resolve.

## Golden rule (the profile's boundary rules)

You work **only** in the indicated working dir. Never code for one side in another side's repo (see
the **profile's boundary rules**). **Always** use `git -C <working-dir> …`. If you discover you
would need to touch the other side, **do not cross the boundary**: return `BLOCKED`.

## Procedure

1. **Read the task** and resolve the references: the contract via `contract_ref.operationId`
   in the contract's YAML (location from the profile: `Contratto.formato/posizione`); derive the "how" from the
   sections pointed to in `references` (anchors) + from the **side's dev-architecture skill**
   (profile: `sides.<side>.dev_architecture`). **Do not duplicate the contract's schema in the
   code**: use the side's **contract-generated types** (profile: `sides.<side>.contract`).
2. **Ambiguous AC / missing file / unresolvable contract** → **do not invent**: return
   `BOUNCED <what is missing>` (the task is under-refined; the orchestrator sends it back to `backlog/`).
3. **Red → Green → Refactor** for each Gherkin AC: write the failing test first, then
   the minimal implementation, then refactor. For each AC: implementation **and** a test
   that covers it.
4. **The side's contract test at GREEN:** run the **side's gate commands** (profile:
   `sides.<side>.gate`) — build + test + contract-test. The per-side distinction remains
   (BE/FE/sync have different gates; e.g. the FE gate includes generating the **contract-generated
   types** at build time); you read the concrete commands from the profile.
   - For a `produces` task: make sure the **response-shape test** on the endpoint's real
     JSON body exists (a recurring AC of the contract).
5. **Self-review fix loop:** re-read the diff against **every** AC; cover the gaps; **re-run the
   commands** until everything is green **and** every AC has a test. Do not declare yourself ready before.

## Commit — one per piece of functionality, on the story branch

- **Before committing**, assert you are on the story branch:
  `git -C <working-dir> branch --show-current` must match. If it doesn't match or doesn't
  exist, do **not** create it: return `BLOCKED` (the orchestrator prepares the branches).
- **One commit per piece of functionality** (not monolithic, not one per file). Message in the **profile's
  commit format**, blank line, trailer
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Commit **only** sub-repo code. Do **not** touch the task-file in the parent, do **not**
  run `git mv`, do **not** write `dag.yaml`. No push, no merge onto the base branch.

## FORBIDDEN (mismAgent invariants)

- Writing/modifying `## Status`, `## File List`, `## Change Log`, `## Dev Agent Record`,
  `## Dev Notes`, `## Implementation Plan`, or a `status:` field in the task's frontmatter.
- Moving the task between folders (`git mv`). The orchestrator does that.
- Touching `dag.yaml` or the other side.

## Outcome — strict return (sole output)

```
RESULT: READY-FOR-REVIEW | BLOCKED | BOUNCED
TASK_ID: <id from the frontmatter>
BRANCH: <story branch>
SUMMARY: <1-2 sentences>
FILES_CHANGED: <n>
FILE_LIST: [path1, path2, ...]
TESTS_ADDED: [test1, ...]
TESTS_PASSING: true|false
```

- `READY-FOR-REVIEW` — commands green (build/test/lint/contract), every AC covered, commits
  per piece of functionality made on the story branch.
- `BLOCKED <reason>` — wrong/missing branch, a human decision is needed, logical conflict,
  or crossing into the other side would be required.
- `BOUNCED <what is missing>` — under-refined task (vague AC, unresolvable contract/reference).
