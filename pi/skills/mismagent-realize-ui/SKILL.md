---
name: mismagent-realize-ui
description: "mismAgent worker block-type skill for `ui`. Realizes a screen as a unit-tested presenter plus a thin view, and proves it renders (automated render test in the gate, or a recorded run-the-app check). Loaded by the worker."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-ui — a thin view over a testable presenter

You realize **one `ui` block**: a screen that consumes read-models (their `view_shape`) and triggers
use-cases. It owns no domain rule; predicates arrive already computed.

## The pattern — split logic from rendering
- **Presenter / state-holder (plain, testable):** every decision the screen makes — what to show in
  each state, which use-case an event calls, when a control is disabled, empty or in error. It holds
  the view state as the framework's native observable state. The `tests_nl` are tested **here**, as
  plain unit tests.
- **Thin view:** only renders presenter state and forwards events; no branch the presenter did not
  decide.

A hand-rolled counter bumped to force a re-render means the state is in the wrong place: move it
into the presenter as observable state.

## Two proofs — the second is not optional
Presenter tests prove the logic, never that the screen renders. A `ui` block needs both:
1. **Presenter tests** from `tests_nl`, green on their own.
2. **A render check**, by the side's `ui_render_check` (profile):
   - automated → a smoke/screenshot test in the gate (containers render without throwing, are sized,
     key elements present and visible);
   - manual → a recorded run-the-app check via `run-app-smoke` (launches the side with the profile's
     `run`, walks the checklist, records evidence in `render-proof/<block-id>/`).

Presenter-green alone is **not done**.

**Render checklist** — apply every item:
- **Sizing:** windows, dialogs and containers are explicitly sized, never left to defaults.
- **Overflow:** long text and lists clip, scroll or ellipsize on purpose.
- **Contrast / visibility:** every control is visible against its background.
- **States:** empty, error and loading each actually render.
- **Reactivity:** an event re-renders through observable state — proven, not assumed.

## TDD, green on its own
Red-green-refactor on the presenter; iterate on the side's gate until green, every `tests_nl`
covered, and the render check passed.

## Return
`PUBLIC_API`: the screen's entry point and the presenter's testable surface.
`NOTE`: the render-check mechanism used and its result.
