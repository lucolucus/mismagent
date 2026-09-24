---
name: mismagent-run-app-smoke
description: "mismAgent build: the recorded render proof for ui blocks \u2014 launches the side's app (profile run), walks each screen with the render checklist, records evidence + sha under render-proof/<block-id>/. Use at a ui block's review or before release."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# run-app-smoke — the render proof, recorded

You produce the **second proof** of a `ui` block (presenter-green alone is not done) by **running
the real app** and recording what you see — clipped or invisible controls are caught only this way.

## Input
- the **ui block(s)** to prove: one block (at its review) or every `ui` block of a slice (before release);
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
   - **re-render** — interact and watch the view actually update.
3. **Record the evidence** in `<output_dir>/features/<feature>/render-proof/<block-id>/`: a screenshot per
   checklist item where the platform allows capture (browser tooling, OS screenshot), otherwise a
   dated observation note per item — **what was checked, what was seen**; a live process or a
   window title alone proves nothing. Evidence is written even when everything passes, plus a
   `sha.txt` holding the sha you ran (`rev-parse HEAD` in the worktree): evidence for another
   sha is no proof.
4. **Verdict per block:**
   - `RENDER-OK` — checklist green, evidence recorded → this is the proof the verifier's step 8
     accepts for a manual `ui_render_check`;
   - `RENDER-FAIL` — findings named (which item, which screen, evidence attached) → routes like a
     review FAIL: the worker reworks the block (max 2 cycles), then re-prove.

## Boundaries
- You write **evidence only**, under `<output_dir>/features/<feature>/render-proof/` — **never** app code,
  never state (`git mv` is the worker-composer's), never the block files.
- You prove **rendering**, not logic — never duplicate the worker's tests or the verifier's AC coverage.

## Outcome — tight handoff
```
RUN-APP-SMOKE: RENDER-OK | RENDER-FAIL | NOT-RUNNABLE
BLOCKS: [<block-id>: OK | FAIL(<checklist item> @ <screen>), ...]
EVIDENCE: <output_dir>/features/<feature>/render-proof/
NOTES: <1-2 sentences — e.g. states not reachable and why>
```
Consumers: **`mismagent-verifier` step 8** (the recorded proof), the worker (rework findings), and
**the user** at release confirmation.
