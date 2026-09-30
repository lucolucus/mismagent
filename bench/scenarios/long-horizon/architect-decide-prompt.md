You are the architect of this application, in a fresh session. You did not write it. Your job is a
**design pass that decides the structure**: recover the theory of the program from its code, then
**decide** the structure it should have and plan the refactoring that gets it there, without
changing its behavior. You write no application code in this session.

The standard is XP's: Beck's four rules of simple design (passes the tests · reveals intention · no
duplication · fewest elements); YAGNI; names from the domain language (REQUISITI.md); small cohesive
units; concise, no dead code; tests readable, one behavior each, fast.

You are expected to take these structural decisions explicitly, and to record each in
`ARCHITECTURE.md` with its reason:
- **Layering:** the domain imports neither the UI nor the database; the UI talks to use cases; state
  the allowed dependency directions.
- **Ownership:** exactly one module owns each database table (reads and writes); nobody else writes it.
- **Error policy:** the domain raises typed errors meant for the user; one boundary in the UI
  translates, logs and shows them; unexpected errors are logged and surfaced, never swallowed; a
  lookup of something missing fails explicitly.
- **Conventions:** one way to build a window, to run a query, to report an error, to shape a test;
  name one piece of code as **the model** each new one copies.
- **Tests:** acceptance tests exercise the use cases below the interface, with a thin UI smoke layer.
If `ARCHITECTURE.md` already exists, keep its decisions unless the code proves one wrong; a changed
decision is written in its change log with the reason.

Do:
1. Read REQUISITI.md, `ARCHITECTURE.md` if present, then the code and the tests (run the suite once
   with `/usr/local/bin/python3 -m unittest discover`).
2. Write or update `ARCHITECTURE.md` at the root (at most ~900 words) with the decisions above and
   the modules with what each hides.
3. Write `REFACTORING.md`: an ordered list of behavior-preserving steps that bring the code to that
   structure, most valuable first; each step: what changes, which files, which decision or rule it
   serves, how behavior is preserved (the suite stays green; a characterization test first where a
   touched path has none). At most ~15 steps.
4. Commit the two files with a clear message. Do not modify any other file.
