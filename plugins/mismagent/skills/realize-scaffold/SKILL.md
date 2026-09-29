---
name: realize-scaffold
description: 'mismAgent worker skill for block type scaffold (greenfield wave 0): the minimal buildable skeleton — build entry, modules, plugins, no-from ADR checks — accepted when the gate runs green on the empty tree, proven discriminating red-green.'
user-invocable: false
---

# realize-scaffold — the buildable skeleton the owners compile against

You realize **ONE scaffold**: the minimal project skeleton for a **side**, so its gate runs
**green on an empty tree** and every later block has something to compile against. Greenfield only: a project that already builds has no scaffold.

## What you create (stack-agnostic — the SHAPE; the stack ADR gives the concrete commands)
- the **build entry**: the wrapper / build descriptor the **stack ADR** names;
- the **module structure** of the module map in **`<output_dir>/architecture.md`** (bounded
  contexts → modules) — directories + empty source sets;
- the **plugins / dev-deps** the gate needs (test runner, the persistence/UI plugins named in the
  stack ADR / infra-notes), pinned to a working version;
- the minimal config so the **gate's build + test phases execute** (a placeholder test is fine, no
  behavior yet);
- the build tool's **standard parallel execution and build cache**, on (the gate's forced re-run
  switch still applies);
- if the side renders UI and the profile's **`ui_render_check`** is **automated**: the
  UI-test dependency/config, wired into the gate (a placeholder smoke test is fine — else `ui`
  blocks arrive with no harness);
- if the side renders UI: **honor the profile's `run` binding** — create exactly what it names (the
  launch task/entry point, and its port only if it names one), so the command launches on the empty
  skeleton — a **contract you satisfy**, not a value you choose; if the skeleton can't honor it,
  report it. A **manual** `ui_render_check`: run `run-app-smoke` once on the skeleton; no launch or no
  capture → report it (the check must become automated).
- if `architecture.md` defines **module boundaries** and `code-rules.md` names a **dependency
  lint**: wire its config and the published-surface check (public signatures against the Published
  Language) so the **gate executes them from wave 0** — the lint config is the module map's
  *executable projection* in this repo (workers maintain it on rename);
- the **`enforced_by` checks without `from`** of the ADRs in your pack (they apply from the start):
  each at its path with its violating and conforming fixture, registered in the gate so it prints
  its ADR and result;
- a **custom check** reading sources enumerates the files git tracks or would track (tracked +
  untracked-not-ignored), never walks the tree (worktrees and build output live under the
  root); the compiler's own source discovery untouched.

## Boundaries — you write NO domain
**Only** the skeleton: no aggregate, port, invariant, business rule or shared domain type (VO,
enum) — those are the reviewed owner blocks **after** you. No module names beyond the
architecture's; no dependencies the stack ADR / infra-notes did not call for.

## Acceptance — the negative space (no ACs, no contract test)
Your only acceptance: **the side's `gate` (profile) runs GREEN on this empty skeleton** — the build
compiles, the test phase executes and the checks above pass. The worker-composer checks exactly
this with the **gate alone** (no verifier) before the owner waves.

**…and you PROVE the gate discriminating, red-green:** before finishing, plant a trivially failing probe test in **each module the gate claims to guard** (at minimum the
deepest domain module, not just the app module), run the gate → see it **RED**, remove/flip the
probe → see it **GREEN**; record the proof as a **FILE** —
`<output_dir>/features/<feature>/gate-proof/<side>/evidence.md`: modules probed, the red excerpt, the green rerun
— then stamp it with
`MM proof record <feature-dir> gate <side> --gate "<the side's gate>" --gate-files <the profile's sides.<side>.gate_files>`
(`MM` = `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mismagent.py"`). A gate green over a failing
test (e.g. a build task that compiles modules but never runs their tests) is a **finding to
report against the profile's gate string**: without this proof every future review is vacuously
green, and readiness refuses the gate.

## TDD note
No behavior to TDD (no `craft` loop): run the **side's gate** → fix the toolchain/config →
green — the smallest passing skeleton, no added scope.

## Return (to the worker)
`SCAFFOLD_READY`: gate green on the empty skeleton? **gate seen RED on the probe, then green
(which modules probed; evidence written)?** no-`from`
checks written and registered? module
structure = the architecture's? `run`
binding honored (UI side)? declared contract locations created (event-schema)? no domain
code introduced? no unrequested deps? yes/no.
