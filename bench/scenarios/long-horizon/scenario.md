# Scenario — long-horizon (S2-lite): does the code stay maintainable, change after change?

Pre-registered on 2026-09-29, before any arm runs. Deliverable: the cash register of the cassa
scenario (`REQUISITI.md` v1 + v2 + v3), then **four change requests** written in advance
(`requisiti-v4…v7`), each touching the cart, the payment, the sales and the reports again. Design
rationale: `docs/rationale/v0.5-hypotheses.md`, `v0.5-core.md`.

## Arms
| arm | what builds | start |
|---|---|---|
| **A** | plain Claude Code, the baseline's `CLAUDE.md`, the simulated user in turns (`bench/converse.py`) | a clone of the baseline run E0 at its tag R2 |
| **C** | A, plus one design pass after each release (`architect-prompt.md` + `refactor-prompt.md` of the baseline scenario) | a clone of E0 at R2 |
| **C′** | A, plus one design pass per release that may also **decide** the structure (`architect-decide-prompt.md`: layering, one owner per table, an error policy, conventions) | a clone of E0 at R2 |
| **B** | mismAgent 0.5, minimal core (`docs/rationale/v0.5-core.md`: structure at birth, error policy, review table for the reviewer, sensors with suppression count, design pass on signal) | from scratch: R0, R1 (v2), R2 (v3) with the same simulated user, then the four requests |

## Step 0 — the judge's noise (before the arms)
The blind quality review (`../baseline/quality-review-prompt.md`) three times on E0's R2 and three
times on the design-passed code (`RegistratoreCassaBaselineDP`, branch `design-pass`). Report the
mean and the spread per dimension. Every score below is the **mean of three** reviews.

## Phases (each arm)
| phase | change | release | budget |
|---|---|---|---|
| CR1 | append `requisiti-v4-sconti.md` | R3 | A $15 · C/C′ $15 + $11 · B $30 |
| CR2 | append `requisiti-v5-pagamenti.md` | R4 | same |
| CR3 | append `requisiti-v6-listini.md` | R5 | same |
| CR4 | append `requisiti-v7-chiusura.md` | R6 | same |

The requests are **fully specified** (requirements + `oracle-s2.md`, the latter appended to the
simulated user's oracle): the scenario measures maintainability, not the interview.

After every release: the rubric score (mean of three), the cumulative external acceptance
(`../cassa-structured/acceptance.md` + `acceptance-s2.md`, sections present so far), the dollars of
the release, the suite size and time, the number of questions the builder asked.

## Hypotheses
| id | hypothesis | pass |
|----|------------|------|
| H1 | A's quality does not improve without a design step: its R6 score ≤ its R2 score (3.1 ± noise) | measured, not a pass/fail of the method |
| H2 | **B's rubric score ≥ 4.0 at every release** R2…R6 | all five |
| H3 | **B's quality slope is flatter than A's** (R6 − R2) | B − A ≥ 0.5 at R6 |
| H4 | **B costs ≤ 4× A per release** (CR1…CR4), and B's cost per request does not climb (CR4 ≤ 1.5 × CR1) | both |
| H5 | acceptance at R6: all 🔴 PASS and ≥ 95% overall, for B; A measured the same way | B |
| H6 | **C < B**: one post-hoc design pass per release does not reach B's score (else the per-slice machinery buys nothing) | B − C ≥ 0.3 at R6 |
| H7 | **C′ < B** on modularity and error handling: deciding the structure late does not match deciding it at birth (else M3/M4 can be a design-pass duty, and the core gets lighter) | B − C′ ≥ 0.5 on those two dimensions at R6 |

The bet of 0.5 is **falsified** if H2, H3, H4 or H6 fails; H7 decides where structure is decided.

**Primary measure of maintainability:** the cost and the defects of each change request (dollars,
rework, acceptance regressions); the review-table score is its proxy.

## Stop rules
A phase that ends without its release tag stops that arm; analyse, never push through. Runs are
strictly sequential (never two arms at once).

## Report
Per arm and per release: rubric (mean, spread), acceptance, $, suite, questions. Then H1–H6 with
one line of evidence each, and what each arm's code looks like at R6 (the three worst problems of
each, from the reviews).
