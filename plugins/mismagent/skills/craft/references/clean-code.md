# Clean code — local readability

**When:** names, flow, effects or comments make the code ambiguous.

- Names from the domain's ubiquitous language; make units, effects and meaning distinguishable where they matter (a duration in ms vs s, find vs find-or-create).
- One name, one concept: don't reuse a name for a different idea.
- A function has an understandable responsibility; extract when it clarifies a concept or separates responsibilities, never to meet a size.
- One level of abstraction per function where it helps the reader follow the flow.
- Make side effects and error handling visible: a query does not mutate; an error is neither swallowed nor returned as a magic value.
- Comments carry reasons, constraints and trade-offs; fix false comments, delete redundant ones.
- Test readability → `tdd.md`.
- Not adopted: universal line or parameter thresholds, "one line is better", a ban on comments, one assertion per test.

Source: [Martin, *Clean Code*, ch. 2–4, 7, 9](https://www.informit.com/store/clean-code-a-handbook-of-agile-software-craftsmanship-9780132639408) — an operative selection, not the whole book.
