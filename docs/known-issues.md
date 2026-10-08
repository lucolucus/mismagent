# Known issues

Accepted for now, with the fix each one would take. Line numbers refer to
`plugins/mismagent/tools/mm.py` at 0.7.2 (`39f617d`); the codex and pi copies are generated from it.

## 0.7.2 — from the code review of `mm built` / `mm review` (2026-10-08)

1. ~~Review drafts can be committed~~ — **fixed**: `mm land` and `mm tag` remove `*.draft.md`
   before committing `reviews/`; `mm review` refuses a draft written before HEAD's commit.

2. ~~`write_header` can overwrite a prose line~~ — **fixed**: a header line needs its colon
   (`Built:`), in `write_header` and in `mm park`'s removal of `Base:`.

3. **A slice started under 0.7.1 comes back as `resume`** (low) — the `## Progress` / old
   `progress.md` signal is gone (~l. 339): a slice in `doing` at upgrade time, finished but with
   no `Built:`, is sent back to the builder instead of to review. It heals itself (the builder
   runs `mm built`, then review). No slice was in `doing` in snastro or mism-aurora on 2026-10-08.
   *Fix, if ever needed:* accept `## Progress` when there is no review and no `Built:` yet.

4. **Release reviews do not note HEAD first** (low) — `agents/mismagent-reviewer.md` (~l. 38) tells
   only the slice review to note `git rev-parse HEAD` at the start; a release reviewer reads it at
   the end, so `mm review`'s "HEAD moved" check cannot catch a commit made during the review.
   *Fix:* the same first step in the release review section.
