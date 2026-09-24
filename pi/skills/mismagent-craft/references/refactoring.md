# Refactoring — transforming safely

**When:** a concrete obstacle has been identified and must be removed.

- Name the obstacle and the expected result before transforming.
- Preserve observable behavior and contracts: public signatures, pinned types, declared errors.
- Small verified steps: one transformation, run the tests, then the next.
- Keep structural change separate from new behavior — never both in one step.
- A smell (duplication, mixed responsibilities, scattered navigation, a long parameter list) calls for a diagnosis; it is not an automatic violation.
- Coverage too thin for the code you are about to move → first add the pertinent test, then transform.
- Stay inside your block: a transformation that needs the other side of a boundary is a normal bounce.
- Stop when the obstacle is gone and the checks pass. Another aesthetic preference does not reopen the loop.
- On a rework: only the findings, no opportunistic refactoring.

Sources: [Fowler, *Refactoring*](https://refactoring.com/) and [*CodeSmell*](https://martinfowler.com/bliki/CodeSmell.html).
