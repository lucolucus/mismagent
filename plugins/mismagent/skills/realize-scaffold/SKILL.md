---
name: realize-scaffold
description: BLOCK-TYPE skill of the mismAgent worker (build, matrix §13.A). Realizes the GREENFIELD scaffold — the minimal buildable skeleton on which every other block compiles (wrapper/build files, module structure, plugins, sourceSets) per the stack ADR + infra-notes. Acceptance is the negative space: the side's gate runs GREEN on the empty skeleton (no domain code, no ACs, no contract test). Built FIRST (wave 0) by the worker-composer. Loaded by the worker when block.type = scaffold.
---

# realize-scaffold — the buildable skeleton the owners compile against

You realize **ONE scaffold**: the minimal project skeleton for a **side**, so that the side's gate
runs **green on an empty tree** and every later block (aggregate, port, …) has something to compile
against. Greenfield only — if the project already builds, this block does not exist. Rationale:
`redesign/composer-spec.md` §13.A (block-type skill) + §15 (wave-0).

## What you create (stack-agnostic — the SHAPE; the stack ADR gives the concrete commands)
- the **build entry**: wrapper / build descriptor (e.g. `gradlew` + `settings`/`build` files,
  `package.json`, `*.csproj`/solution) — read the concrete stack from the **stack ADR**;
- the **module structure** the architecture chose (the bounded contexts → modules, §0(b) of the
  architect) — directories + empty sourceSets, **no domain logic**;
- the **plugins / dev-deps** the gate needs (test runner, the persistence/UI plugins named in the
  stack ADR / infra-notes), pinned to a working version;
- the minimal config so the **gate's build + test phases execute** (an empty/placeholder test is fine
  — the point is the toolchain runs, not that there is behavior).

## Boundaries — you write NO domain
You create **only** the skeleton: no aggregate, no port, no invariant, no business rule. Those are the
owner blocks that come **after** you. Do not invent module names beyond the architecture's; do not add
dependencies the stack ADR / infra-notes did not call for (frugality: the smallest skeleton the gate
needs).

## Acceptance — the negative space (no ACs, no contract test)
Your only acceptance is: **the side's `gate` (profile) runs GREEN on this empty skeleton** — build
compiles, test phase executes (even with zero/placeholder tests), `enforced_by`-relevant dirs exist
where the architecture put them. The worker-composer gates exactly this before starting the owner waves.

## TDD note
There is no behavior to TDD here. The loop is: run the **side's gate** → fix the toolchain/config →
green. Climb the frugality ladder (smallest skeleton that makes the gate pass), never adding scope.

## Return (to the worker)
`SCAFFOLD_READY`: gate green on the empty skeleton? module structure = the architecture's? no domain
code introduced? no unrequested deps? yes/no.
