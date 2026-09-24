---
name: mismagent-realize-scaffold
description: "mismAgent worker block-type skill (type scaffold, greenfield wave 0): the minimal buildable skeleton \u2014 build entry, modules, plugins, the no-from ADR checks \u2014 whose acceptance is the gate green on the empty tree, proven discriminating red-green."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# realize-scaffold — the buildable skeleton the owners compile against

You realize **ONE scaffold**: the minimal project skeleton for a **side**, so that the side's gate
runs **green on an empty tree** and every later block (aggregate, port, …) has something to compile
against. Greenfield only — if the project already builds, this block does not exist.

## What you create (stack-agnostic — the SHAPE; the stack ADR gives the concrete commands)
- the **build entry**: the wrapper / build descriptor the **stack ADR** names;
- the **module structure** the architecture chose (the bounded contexts → modules — read it from
  **`<output_dir>/architecture.md`**, the project module map) — directories + empty source sets,
  **no domain logic**;
- the **plugins / dev-deps** the gate needs (test runner, the persistence/UI plugins named in the
  stack ADR / infra-notes), pinned to a working version;
- the minimal config so the **gate's build + test phases execute** (an empty/placeholder test is fine
  — the point is the toolchain runs, not that there is behavior);
- if the side renders UI and the profile's **`ui_render_check`** is an **automated** check: the
  UI-test dependency/config, wired so the gate can execute it (a placeholder smoke test is fine —
  the render-proof toolchain must run from wave 0, or the `ui` blocks arrive with no harness);
- if the side renders UI: **honor the profile's `run` binding** — create exactly what it names (the
  launch task/entry point and the pinned port), so the command launches on the empty skeleton. It
  is a **contract you satisfy**, not a value you choose — if the skeleton can't honor it, report
  it. *(Proving it renders stays `run-app-smoke`'s job, at the first `ui` block.)*
- if `architecture.md` defines **module boundaries** and `code-rules.md` names a **dependency
  lint**: wire its config so the **gate
  executes it from wave 0** — the lint config is the *executable projection of the module map*,
  and it lives in this repo (the workers maintain it on rename, like any build file);
- the **`enforced_by` checks without `from`** of the ADRs in your pack (they apply from the start):
  each at its path with its violating and conforming fixture, registered in the gate so it prints
  its ADR and result — `MM lint` defers them until you are done.

## Boundaries — you write NO domain
You create **only** the skeleton: no aggregate, no port, no invariant, no business rule. Those are the
owner blocks that come **after** you. Do not invent module names beyond the architecture's; do not add
dependencies the stack ADR / infra-notes did not call for (frugality: the smallest skeleton the gate
needs).

## Acceptance — the negative space (no ACs, no contract test)
Your only acceptance is: **the side's `gate` (profile) runs GREEN on this empty skeleton** — the build
compiles and the test phase executes (even with zero/placeholder tests) and the checks above pass.
No ACs, no contract test. The worker-composer gates exactly this — the **gate alone** — before the
owner waves; it does not send a scaffold through the verifier.

**…and you PROVE the gate discriminating, red-green:** before finishing,
plant a trivially failing probe test in **each module the gate claims to guard** (at minimum the
deepest domain module, not just the app module), run the gate → see it **RED**, remove/flip the
probe → see it **GREEN**; record the proof as a **FILE** —
`<output_dir>/features/<feature>/gate-proof/<side>/evidence.md`: modules probed, the red excerpt, the green rerun —
never only in your return (handoffs are files) — then stamp it with
`MM proof record <feature-dir> gate <side> --gate "<the side's gate>" --gate-files <the profile's sides.<side>.gate_files>`
(`MM` = `python3 .agents/skills/mismagent-worker-composer/scripts/mismagent.py`). A gate that stays green
over a failing test (a per-app build task that compiles dependency modules but never runs their
tests) is a **finding to report against the profile's gate string**:
without this proof every future review is vacuously green, and readiness refuses the gate.

## TDD note
There is no behavior to TDD here. The loop is: run the **side's gate** → fix the toolchain/config →
green. Climb the frugality ladder (smallest skeleton that makes the gate pass), never adding scope.

## Return (to the worker)
`SCAFFOLD_READY`: gate green on the empty skeleton? **gate seen RED on the probe, then green
(discriminating-power proof — which modules probed; `gate-proof/<side>/evidence.md` written)?** no-`from`
checks written and registered? module
structure = the architecture's? `run`
binding honored (UI side)? declared contract locations created (event-schema)? no domain
code introduced? no unrequested deps? yes/no.
