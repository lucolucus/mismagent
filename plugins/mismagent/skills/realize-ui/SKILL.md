---
name: realize-ui
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes a `ui` block — a screen/component that consumes read-models (their view_shape) and triggers use-cases. Splits the block into a TESTABLE state-holder/presenter (the logic, unit-tested from tests_nl) + a THIN view that only renders presenter state and forwards events. Carries the render-check (sizing/overflow/contrast/state-rendering) that presenter tests and "it compiles" cannot prove. Loaded by the worker when block.type = ui.
---

# realize-ui — the thin view over a testable presenter

You realize **ONE `ui` block**: a screen/component that **consumes read-models** (their `view_shape`)
and **triggers use-cases** (the application-services). Like a read-model it owns **no domain rule** —
it decides nothing the domain owns; predicates come already computed. Rationale:
`redesign/composer-spec.md` §1·§8; friction-log #13 (the single most-confirmed gap in the flow).

## The pattern — split logic from rendering
A `ui` block is **two parts, never one**:
- **State-holder / presenter (plain, testable):** every *decision* the screen makes — what to show
  per state, how an event maps to a use-case call, the disabled/empty/error condition. It holds the
  view state as the **framework's native observable state** (Compose `State`/`mutableStateOf`, a
  signal, an observable, a store…). The **`tests_nl` are tested HERE**, as plain unit tests.
- **Thin view (the `@Composable` / component):** **only renders** presenter state and **forwards**
  events. No logic, no branch the presenter didn't already decide.

**No manual-invalidation hack.** If you reach for a hand-rolled `tick`/counter-bump to force a
re-render, the state is in the wrong place — move it into the presenter as observable state. A manual
invalidation is a smell, not a solution (friction-log #13).

## The check — two proofs, the second is NOT optional
Presenter unit-tests + "the view compiles" prove the **logic**, never that the screen **renders
correctly**. The confirmed gap (3 runtime bugs across 2 slices — clipped keypad, wrapped cart row,
invisible white-on-white button — invisible to 100+ green tests) lives exactly here. A `ui` block
needs **both**:
1. **Presenter tests** (from `tests_nl`) — the logic, green on its own.
2. **Render-check** — the screen renders right. Its **mechanism comes from the side's profile `ui`
   gate** (`ui_render_check`):
   - the side has a **UI-test capability** → an automated **smoke/screenshot test** in the gate
     (containers render without throwing, are sized, key elements present & visible);
   - it has **none** → a **recorded run-the-app render-check** (the boundary proof is a human render,
     written down — **never silent**).

   **Presenter-green alone is NOT done.**

**Render checklist** — the confirmed failure modes, generalized. Self-apply every one:
- **Sizing:** windows / dialogs / containers are **explicitly sized**, never left to defaults
  (defaults → clipped or tiny).
- **Overflow:** long text / lists clip-or-scroll-or-ellipsize **on purpose**, never silently wrap or
  overflow the panel.
- **Contrast / visibility:** every control is visible against its background (no white-on-white, no
  blend-into-bar).
- **State rendering:** empty / error / loading each actually render (states before the pretty UI).
- **Recomposition wiring:** an event re-renders **via observable state** — proven, not assumed.

## TDD + green on its own
`tdd` red-green-refactor on the **presenter**; self-review fix-loop on the **side's gate** until
green, every `tests_nl` covered, **and** the render-check passed (gate UI test green, or the
run-the-app check recorded).

## Return (to the worker)
`PUBLIC_API`: the screen's entry point + the presenter's testable surface.
`NOTE`: the render-check mechanism used (gate UI test | recorded run-the-app) and its result.
