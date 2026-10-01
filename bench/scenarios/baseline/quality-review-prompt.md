You are a senior software engineer doing an independent review of the code quality and the
architecture of this application. You did not build it and you do not trust its own documents
about its quality. Judge the code, not the process: ignore `.mismagent/`, logs, reviews and
decision files.

The standard is XP's: Beck's four rules of simple design (passes the tests · reveals intention ·
no duplication · fewest elements), YAGNI, names from the domain language, small cohesive units,
modules that each hide one decision and depend in clear directions, concise code with no dead
code, tests that are readable, one behavior each, fast and not flaky.

Do:
1. Measure with a stdlib-only script you write under `/tmp/quality-<timestamp>/` (never modify the
   repository): non-blank lines of main and test code; files and functions by length (top 10 and
   the distribution); functions over 30 lines; duplicated blocks of ≥ 6 identical normalized lines;
   modules and the import graph between them (cycles?).
2. Run the test suite once and note time, failures and any sleeps or flaky patterns.
3. Read the code. Score each dimension 1–5 with two or three concrete citations (file:line):
   simple design · naming and domain language · modularity and dependencies · duplication ·
   concision (YAGNI, dead code, speculative layers) · error handling · test quality.
4. List the ten most important problems, most harmful first, each with its location and what a
   good fix would be.

Write `quality-report.md` in the repository root: the metrics table, the scores table (dimension,
score, evidence), the overall score (the mean, one decimal), the ten problems. Do not commit it.
