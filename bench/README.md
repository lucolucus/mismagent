# bench — compare runs of the same deliverable across mismAgent versions

`score.py` reads several run folders that built the **same** `REQUISITI.md` and prints one
Markdown table (runs as columns, metrics as rows). Zero cost and deterministic: Python 3 stdlib
only, no LLM, no network, no build tool run, nothing written into the runs (git is only read).

```sh
python3 bench/score.py ~/projects/mismagent-test/RegistratoreCassa{2,3,4,5}          # table
python3 bench/score.py ~/projects/mismagent-test/RegistratoreCassa{2,3,4,5} --json   # machine output
python3 -m unittest discover -s bench/tests -v                                         # self-tests
```

A metric that cannot be computed prints `n/a`; `--json` carries the reason (`{"n/a": "…"}`).
It never guesses: a friction entry whose class is neither core nor profile is `unclassified`.

## What it measures
| metric | source |
|---|---|
| mismAgent version | `~/.claude/plugins/installed_plugins.json` entries whose `projectPath` is the run (the `installPath` version segment) + any `mismAgent vX.Y` in the log header |
| requirements coverage | IDs from the ID column of `REQUISITI.md`'s tables (`RF1.1`, `RNF3`, `RB2`, …; 🔴 = high). Cited in: every text file under `.mismagent/` (model), test sources, main sources. Understands `RF6.*` and ranges `RF2.1–RF2.5` / `RF2.1-2.5` |
| tests | test files with ≥1 case and cases (`@Test`, Kotlin backtick funs, `def test_`, `it(`/`test(`, `[Fact]`/`[Test]`, …) per language |
| code size | non-blank lines of main vs test sources; test = a `test`/`tests`/`*Test` source-set dir or a test-named file. Skips `build/`, `.gradle/`, `node_modules/`, `.git/`, `generated/`, `bin/`, `obj/`, … |
| friction | `MISMAGENT-LOG.md`: headings `## #N — …` (any level, dated headings too) with a `Class:`/`Classification:`/`Tipo:` line or a `(core, …)` note in the heading, **or** a table with a `CORE/PROFILO` column. core / profile / both / unclassified; per movement from the `When`/`Quando` field (or a `## Movimento: x` section) |
| process | under `.mismagent/` (any layout): block/task files per `todo/doing/done` (+`backlog`), `open-questions/`, `rework/`, `integrated/*.json`, `### D-NNNN` in `decisions.md`, numbered ADR files in `decisions/` |
| git | commits (all refs), first/last commit date, span in days, local branches |

## Limits
- Citation counts measure **traceability**, not correctness: a test citing `RF3.2` may not test it,
  and an untagged test covering it is not seen.
- Test/LOC detection is path- and marker-based; exotic layouts or frameworks may be missed.
- Friction class and movement come from free text: a `When` naming no movement is `?`.
- The **gate is not run** (`gate` row is always `n/a`): running `./gradlew …` would write build
  output into the runs. Future work: copy the run to a temp dir and execute the profile's `gate`
  there, recording pass/fail and duration.

# run.py — the headless build runner

`run.py` re-invokes the worker-composer headless until the **tool** says the feature is finished,
or a dollar cap is reached. Runner-side only: the core never depends on it. Stdlib only.

```sh
python3 bench/run.py --project ~/projects/mismagent-test/RegistratoreCassa6 --feature cassa \
  --plugin-dir plugins/mismagent --total-usd 40 --per-firing-usd 8 [--model opus] \
  [--prompt-file sim-user.md] [--integration integration/cassa] [--feature-dir <F>]
python3 -m unittest discover -s bench/tests -v     # self-tests: a simulated claude CLI, never the real one
```

- **Firings, serial.** `claude -p --plugin-dir <plugin> --output-format json --max-budget-usd
  <min(per-firing, remaining)> "/mismagent:worker-composer <feature>"` in `--project`, the later ones
  with `--resume <session_id>`, always with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`.
  `--prompt-file` text is appended to the command (e.g. simulated-user rules).
- **Cost** = the deltas of `total_cost_usd` (cumulative on resume). Missing, invalid or decreasing →
  stop `cost-invalid`, never a silent zero. The cap follows the CLI's accounting, not the invoice.
- **Minimum Claude Code: 2.1.277** — earlier versions report each invocation's own cost, not the
  cumulative one, so the deltas would be wrong. `claude --version` is read at start; older or
  unreadable → stop `cli-version` before any firing.
- **When to stop** — after each firing it reads `mismagent.py status F --integration B` (`outcome`),
  never the report text (also once before the first firing): `done` · `idle` (only work waiting on a
  decision or an external condition) · `anomaly` · `no-progress` (two consecutive firings changed no
  structural state: state folders, block files and manifest, `integrated/`, review proofs, `rework/`,
  open questions, `pre-release.md`, spike evidence (content), the trees of the `block/*`/`spike/*` branch tips,
  the uncommitted changes (`git status --porcelain` + content) of their worktrees — timestamps,
  reports, logs, ledgers, `decisions.md` and bookkeeping commits ignored) · `budget` (total spent) ·
  `cli-error` / `cli-version` / `status-error` (diagnostic, with the tail of the output). A firing that exhausted its
  own budget continues while the total lasts.
- **Output**: one JSON summary `{outcome, reason, firings, total_cost_usd, session_id, log:[{n,
  cap_usd, cost_usd, subtype, is_error, status, progress}]}`; exit 0 on `done`/`idle`, else 1.
- No timeout, no polling, no sleep, no automatic recovery: every doubt is a stop with its reason.

Headless firings cannot answer permission prompts: pass `--permission-mode` (e.g. `bypassPermissions`,
only on an isolated project you are willing to let the agent modify freely).
