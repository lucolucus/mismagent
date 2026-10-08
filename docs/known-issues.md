# Known issues

Accepted for now, with the fix each one would take. Line numbers refer to
`plugins/mismagent/tools/mm.py` at 0.7.2 (`39f617d`); the codex and pi copies are generated from it.

## 0.7.2 — from the code review of `mm built` / `mm review` (2026-10-08)

1. **Review drafts can be committed** (medium) — `cmd_review` (~l. 692) deletes
   `.mismagent/reviews/<target>.draft.md` only when it succeeds without `--body`. After a refusal
   (HEAD moved, bad score, dirty tree, wrong verdict) the draft stays: `mm land` and `mm tag`
   (`git add -A -- .mismagent/reviews`, ~l. 707) commit it, and a later `mm review` with no new
   draft — e.g. the architect's DIRECT — takes the stale one as its body.
   *Fix:* land and tag skip or delete `*.draft.md`; `mm review` refuses a draft older than HEAD.

2. **`write_header` can overwrite a prose line** (low) — its header pattern (~l. 565) matches any
   line before the first `## ` that starts with `kind|release|examples|base|after|built`, colon
   or not: a description line "Built on the cart model…" becomes `Built: 1`, and a line starting
   "After …" becomes the insertion point.
   *Fix:* require `\s*:` after the key.

3. **A slice started under 0.7.1 comes back as `resume`** (low) — the `## Progress` / old
   `progress.md` signal is gone (~l. 339): a slice in `doing` at upgrade time, finished but with
   no `Built:`, is sent back to the builder instead of to review. It heals itself (the builder
   runs `mm built`, then review). No slice was in `doing` in snastro or mism-aurora on 2026-10-08.
   *Fix, if ever needed:* accept `## Progress` when there is no review and no `Built:` yet.

4. **Release reviews do not note HEAD first** (low) — `agents/mismagent-reviewer.md` (~l. 38) tells
   only the slice review to note `git rev-parse HEAD` at the start; a release reviewer reads it at
   the end, so `mm review`'s "HEAD moved" check cannot catch a commit made during the review.
   *Fix:* the same first step in the release review section.
