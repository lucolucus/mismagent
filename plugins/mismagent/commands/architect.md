---
description: Invoke mismAgent's architect (model movement) — dispatches the mismagent-architect subagent. TWO DISPATCHES, decided by the PROJECT trunk, never by the feature folder. FOUNDATIONAL (once per project, when <output_dir>/architecture.md or code-rules.md is missing or the profile's gate is still TBD): two-pass headless DISCOVERY (stack + architecture style + code-writing rules + infra deliberated WITH you) then writes architecture + ADRs + the project definition files and finalizes the gate and the UI sides' run binding. FEATURE (trunk already present): skips pass-1 and writes only what this feature adds — its boundary decisions. In greenfield it also AUTHORS the codebase's dev-architecture (style memory) before the first domain wave — a targeted dispatch, never a pass-1 re-run. Use in model after the tactical model.
argument-hint: "[feature]"
---

**Decide the dispatch BEFORE dispatching anything — read the PROJECT trunk, not the feature.**
The foundational deliberation happens **once per project**. Look at `<output_dir>/architecture.md`,
`<output_dir>/code-rules.md`, `<output_dir>/decisions/` and the profile's `gate`:

- **Trunk absent** (`architecture.md` or `code-rules.md` missing, **or** `gate` still reads
  `manual — TBD after the stack ADR`) → **FOUNDATIONAL dispatch**, the two-pass below.
- **Trunk present** → **FEATURE dispatch**. Dispatch with `DISPATCH: feature` and the trunk as
  given, **plus the same model inputs the foundational dispatch gets** — the feature's
  `product-brief.md` and `features/<feature>/tactical-model.md`, the project's `context-map.md`, the
  per-side guides, existing `architetture/*`. Without the tactical model it has nothing to draw this
  feature's boundaries from. The architect writes **only** what this feature adds — its boundary
  decisions, and a feature-scoped ADR if one is genuinely needed. Do **not** run pass-1. State the trunk to me
  ("stack, style and code rules are fixed by `decisions/NNNN-…`; I'm not reopening them").

**Never infer "the trunk is missing" from the feature folder.** A new feature's
`features/<feature>/` is empty **by construction**; reading that emptiness as "nothing decided yet"
is exactly what re-deliberated the stack and rewrote the profile on every feature. `decisions/` and
`architetture/` live in the `<output_dir>` **root**, not under the feature.

**Reopening a foundational decision** happens only if I ask, and then it is an **amendment**: a
superseding ADR in `<output_dir>/decisions/`, deliberated at the same checkpoint discipline, plus
the edit to `architecture.md`/`code-rules.md` it implies — never a silent rewrite. A contextless
pass-1 re-run would re-propose choices already deliberated, ignorant that some ADRs are the
*conclusions of an adverse review* (supersedes), not open questions. The **style pass** (§3½ of the
agent: authoring the codebase's dev-architecture before the first domain wave) is a legitimate
targeted dispatch on a finalized trunk — it is not a pass-1 re-run. Same resume rule as
`/mismagent:model`; the single command is not exempt (friction-log-4 #14).

**The FOUNDATIONAL dispatch — two-pass (the agent is headless).** Dispatch the
**`mismagent-architect`** subagent (Agent tool) for `$ARGUMENTS` (or the current feature) with
`DISPATCH: foundational` and the model inputs: the feature's `product-brief.md` and
`features/<feature>/tactical-model.md`, the project's `<output_dir>/context-map.md`, the per-side
guides, existing `architetture/*`. Pass-1 returns `STACK_PROPOSAL` / `ARCH_PROPOSAL` (style +
quality drivers + the code-writing rules that follow) / `INFRA_QUESTIONS` — bring those to me to
decide, then re-dispatch pass-2 to write the ADRs/architecture, the project definition files
(`<output_dir>/architecture.md` + `code-rules.md`), `<output_dir>/infra-notes.md`, and finalize the
profile `gate` (incl. the dependency lint) **and the UI sides' `run` binding**.
See `agents/mismagent-architect.md`.
