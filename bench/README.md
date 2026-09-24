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
