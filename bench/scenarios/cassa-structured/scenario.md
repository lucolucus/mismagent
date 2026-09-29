# Scenario — cassa-structured (three releases, a change request, a second feature)

A validation run with its hypotheses, phases, budgets and stop rules fixed **before** it starts, so
the result is read against them and runs stay comparable. Deliverable: the cash register of
`REQUISITI.md` (runs 2–7). Runner: `run-scenario.sh` (this folder). Harness: mismAgent ≥ v0.25.3.

## Hypotheses (pre-registered)
| id | hypothesis | measured by | pass |
|----|------------|-------------|------|
| H1 | every phase ends with its expected outcome within its budget | `phases.jsonl` | all phases |
| H2 | the composer's own session is a minority of each build phase's tokens | `cost.py` per build phase | ≤ 35% |
| H3 | resuming never needs a judgment call (v0.25.3 resume facts) | frictions + decision notes about resume ambiguity | 0 |
| H4 | the v2 change reaches the already-built R0 code **through the method** (changed or new blocks, re-reviewed), not by a silent edit | git log of integrated code after phase C: every commit on a `block/*` branch; `rework/` or new blocks for the VAT change; ≥1 test citing `RB4` | yes |
| H5 | the second feature reuses the trunk: no new stack/architecture ADR, the profile only amended; the cross-feature link (a sale → a stock movement) is a pinned boundary with a contract test in the gate | `decisions/` diff, profile diff, `building-blocks.yaml` boundaries of `magazzino` | yes |
| H6 | the released app passes the external acceptance (`acceptance.md`, written before the run) | `acceptance-report.md` | ≥ 90% PASS, 100% of 🔴 |
| H7 | frictions stay few and new | `MISMAGENT-LOG.md` per phase | ≤ 5 new `core` per phase |

## Phases
| phase | what | command | budget | expected outcome |
|-------|------|---------|-------:|------------------|
| A1 | explore `cassa` | `/mismagent:explore …` | $6 | profile, brief, context-map |
| A2 | model `cassa` (R0, R1 per the policy's cut) | `/mismagent:model cassa` | $14 | manifest, lint clean |
| B | build → **R0 confirmed** | `run.py --until-release R0` | $60 | `released` |
| C | change request: append `requisiti-v2.md` to REQUISITI.md; the user asks to take it in | `/mismagent:model cassa` + the change prompt | $15 | model + manifest updated, lint clean |
| D | build → **R1 confirmed** | `run.py --until-release R1` | $50 | `released` |
| E1 | second feature: append `requisiti-v3-magazzino.md`; explore `magazzino` | `/mismagent:explore …` | $8 | feature folder, context-map amended |
| E2 | model `magazzino` (one release) | `/mismagent:model magazzino` | $14 | manifest, lint clean |
| E3 | build → **the magazzino release confirmed** | `run.py --feature magazzino --until-release <its release>` | $50 | `released` |
| F | external acceptance at the final tag, fresh session, **no plugin** | `acceptance-prompt.md` | $10 | `acceptance-report.md` |

Total cap: **$227**. Phases run strictly in sequence; never two runs at once (a shared weekly limit
cut runs 6 and 7 mid-phase when they ran in parallel).

## Stop rules
- A phase that ends with any other outcome than expected (budget, no-progress, anomaly, cli-error,
  a missing artifact) **stops the scenario**: analyse, fix the harness if it is the method's fault,
  then resume from that phase (`run-scenario.sh --from <phase>`). Never push through.
- The simulated user follows `sim-policy.md` only; a question it does not cover is answered with
  the simplest option the flow proposes and logged as a friction (`Class: profile`), so the policy
  grows between runs instead of drifting inside one.

## After each phase
`run-scenario.sh` appends one line to `phases.jsonl` (phase, outcome, cost, sessions, start/end,
frictions so far) and commits the run folder. After the last phase: `cost.py` per build phase,
`score.py` against runs 5–6, and the report below.

## Report template
1. Hypotheses H1–H7: pass/fail, one line of evidence each.
2. Cost per phase (table) and per release; composer share per build phase.
3. The change request (C–D): what the method did with it, step by step; what it missed.
4. The second feature (E): what was reused, what was re-decided, the cross-feature boundary.
5. Acceptance: PASS/FAIL per scenario; each FAIL traced to a block, a review, or the method.
6. New frictions → proposed core changes (distilled, generic), ranked.
