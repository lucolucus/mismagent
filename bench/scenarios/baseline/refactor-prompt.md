You are the builder, in a fresh session. Read `ARCHITECTURE.md` and `REFACTORING.md` at the root,
then the code they name.

Execute the refactoring steps of `REFACTORING.md` in order. Rules:
- **Behavior is preserved.** The whole suite (`/usr/local/bin/python3 -m unittest discover`) is
  green before and after every step. Where a step touches a path no test covers, write a
  characterization test first. Do not change what the user sees or what is stored.
- One commit per step, message naming the step.
- Leave the code at the standard `ARCHITECTURE.md` states: simple design, no duplication, names from
  the domain, small cohesive units, no dead code. Tests are refactored too.
- If a step turns out wrong or harmful, skip it and say why in `REFACTORING.md` (commit that note).
- If the code ends up differing from `ARCHITECTURE.md`, update `ARCHITECTURE.md` so it tells the truth.
- Do not add features. Never push.

When all steps are done or skipped, reply with a short summary: steps done, steps skipped and why,
test count before and after.
