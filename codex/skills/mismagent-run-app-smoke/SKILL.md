---
name: mismagent-run-app-smoke
description: "mismAgent build movement \u2014 the RENDER PROOF for ui blocks (friction-log #13, the most-confirmed gap: 3 runtime layout bugs invisible to 100+ green presenter tests). LAUNCHES the side's app for real (profile sides.<side>.run), walks the ui blocks' screens with realize-ui's render checklist (sizing/overflow/contrast/state-rendering/recomposition) and RECORDS the evidence (screenshots/notes) in <output_dir>/features/<feature>/render-proof/<block-id>/ \u2014 the recorded proof mismagent-verifier step 8 demands when ui_render_check is manual. Writes evidence only, never app code. Use at D1 of a ui block (the worker-composer invokes it there itself when the side's ui_render_check is manual and the proof is missing), or on the whole slice before confirming the release."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# run-app-smoke — the render proof, recorded

You produce the **second proof** of a `ui` block (realize-ui: *"presenter-green alone is NOT done"*)
by **running the real app** and recording what you see. Three confirmed bugs across two slices —
clipped keypad, wrapped cart row, invisible white-on-white button — were caught **only** this way;
until now the "manual run-the-app (recorded)" proof was on the honor system. You mechanize it.

## Input
- the **ui block(s)** to prove: one block (at D1) or every `ui` block of a slice (before release);
- the **active profile**: `sides.<side>.run` (how to launch the side locally) and `ui_render_check`;
- the block specs (`blocks/<ctx>/*/<id>.md`) + `UI/ux-proposal.md` (how to reach each screen).

## Procedure
1. **Launch the app** with the profile's `run` command (background; respect `toolchain`). If the
   profile has **no `run` binding**, stop and say so — do **NOT** fake the proof; the render-check
   stays **owed** and the block cannot pass a manual `ui_render_check` without it.
2. **Reach each block's screen** (the block spec + ux-proposal name it) and apply **realize-ui's
   render checklist**, item by item:
   - **sizing** — windows/dialogs/containers explicitly sized, nothing clipped or tiny;
   - **overflow** — long text/lists clip-or-scroll-or-ellipsize on purpose;
   - **contrast/visibility** — every control visible against its background;
   - **state rendering** — empty / error / loading actually render (drive the app into each state
     where the seams allow it);
   - **recomposition** — interact and watch the re-render actually happen.
3. **Record the evidence** in `<output_dir>/features/<feature>/render-proof/<block-id>/`: a screenshot per
   checklist item where the platform allows capture (browser tooling, OS screenshot), otherwise a
   dated observation note per item — **what was checked, what was seen**. Evidence is written even
   when everything passes (the proof of green is the point, not just the bugs).
4. **Verdict per block:**
   - `RENDER-OK` — checklist green, evidence recorded → this is the proof the verifier's step 8
     accepts for a manual `ui_render_check`;
   - `RENDER-FAIL` — findings named (which item, which screen, evidence attached) → routes like a
     D1 FAIL: the worker reworks the block (max 2 cycles), then re-prove.

## Boundaries
- You write **evidence only**, under `<output_dir>/features/<feature>/render-proof/` — **never** app code,
  never state (`git mv` is the worker-composer's), never the block files.
- You prove **rendering**, not logic: presenter behavior is the worker's tests, AC coverage is the
  verifier's. Don't duplicate their checks.

## Outcome — tight handoff
```
RUN-APP-SMOKE: RENDER-OK | RENDER-FAIL | NOT-RUNNABLE
BLOCKS: [<block-id>: OK | FAIL(<checklist item> @ <screen>), ...]
EVIDENCE: <output_dir>/features/<feature>/render-proof/
NOTES: <1-2 sentences — e.g. states not reachable and why>
```
Consumers: **`mismagent-verifier` step 8** (the recorded proof), the worker (rework findings), and
**the user** at release confirmation.
