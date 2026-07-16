---
name: realize-scaffold
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes the GREENFIELD scaffold — the minimal buildable skeleton on which every other block compiles (wrapper/build files, module structure, plugins, sourceSets) per the stack ADR + infra-notes. Acceptance is the negative space: the side's gate runs GREEN on the empty skeleton (no domain code, no ACs, no contract test). Built FIRST (wave 0) by the worker-composer. Loaded by the worker when block.type = scaffold.
---

# realize-scaffold — the buildable skeleton the owners compile against

You realize **ONE scaffold**: the minimal project skeleton for a **side**, so that the side's gate
runs **green on an empty tree** and every later block (aggregate, port, …) has something to compile
against. Greenfield only — if the project already builds, this block does not exist. Rationale:
`redesign/composer-spec.md` §13 (table A — block-type skills) + §15 (the Phase-2 wave-0 line).

## What you create (stack-agnostic — the SHAPE; the stack ADR gives the concrete commands)
- the **build entry**: wrapper / build descriptor (e.g. `gradlew` + `settings`/`build` files,
  `package.json`, `*.csproj`/solution) — read the concrete stack from the **stack ADR**;
- the **module structure** the architecture chose (the bounded contexts → modules — read it from
  **`<output_dir>/architecture.md`**, the project module map) — directories + empty sourceSets,
  **no domain logic**;
- the **plugins / dev-deps** the gate needs (test runner, the persistence/UI plugins named in the
  stack ADR / infra-notes), pinned to a working version;
- the minimal config so the **gate's build + test phases execute** (an empty/placeholder test is fine
  — the point is the toolchain runs, not that there is behavior);
- if the side renders UI and the profile's **`ui_render_check`** is an **automated** check: the
  UI-test dependency/config, wired so the gate can execute it (a placeholder smoke test is fine —
  the render-proof toolchain must run from wave 0, or the `ui` blocks arrive with no harness);
- if the side renders UI: **honor the profile's `run` binding** — create exactly what it names (the
  launch task/entry point and the pinned port), so the command launches on the empty skeleton. The
  binding was pinned *before you existed* (the architect finalized it with the gate): it is a
  **contract you satisfy**, not a value you choose — if the skeleton can't honor it, that is a
  finding to report, not a license to pick another command/port (friction-log-4 #15). *(Proving it
  renders stays `run-app-smoke`'s job, at the first `ui` block.)*
- if a cross-deploy boundary declares **`contract_form: event-schema`** with `schema_paths` in this
  side's tree: create that **contract location** (dirs + build wiring for schema
  compilation/codegen the stack ADR names) — the contract files are an output of this scaffold,
  which is why Phase 1 deferred their check (friction-log-4 #16);
- if `architecture.md` defines **module boundaries** and `code-rules.md` names a **dependency
  lint** (Konsist/ArchUnit, dependency-cruiser, import-linter, …): wire its config so the **gate
  executes it from wave 0** — the lint config is the *executable projection of the module map*,
  and it lives in this repo (the workers maintain it on rename, like any build file).

## Boundaries — you write NO domain
You create **only** the skeleton: no aggregate, no port, no invariant, no business rule. Those are the
owner blocks that come **after** you. Do not invent module names beyond the architecture's; do not add
dependencies the stack ADR / infra-notes did not call for (frugality: the smallest skeleton the gate
needs).

## Acceptance — the negative space (no ACs, no contract test)
Your only acceptance is: **the side's `gate` (profile) runs GREEN on this empty skeleton** — the build
compiles and the test phase executes (even with zero/placeholder tests). No ACs, no contract,
no `enforced_by` (those arrive with the owner blocks). The worker-composer gates exactly this — the
**gate alone** — before starting the owner waves; it does not send a scaffold through the verifier.

## TDD note
There is no behavior to TDD here. The loop is: run the **side's gate** → fix the toolchain/config →
green. Climb the frugality ladder (smallest skeleton that makes the gate pass), never adding scope.

## Return (to the worker)
`SCAFFOLD_READY`: gate green on the empty skeleton? module structure = the architecture's? `run`
binding honored (UI side)? declared contract locations created (event-schema)? no domain
code introduced? no unrequested deps? yes/no.
