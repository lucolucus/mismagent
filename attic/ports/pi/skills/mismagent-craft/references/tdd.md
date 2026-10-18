# TDD — the next test

**When:** choosing the next test, diagnosing a red, judging a brittle or unreadable test.

- Turn one required behavior (an acceptance criterion, an invariant, a `tests_nl` line) into one concrete example.
- Watch it fail **for the expected reason**: a compile error or a broken fixture is not the red you want.
- Make it pass with the minimum; restructure only on green.
- Name, arrangement, action and outcome make the verified behavior evident: essential fixtures only, diagnostic assertions (a failure says what broke).
- Assert results and contractual interactions, not incidental details (private calls, an order nobody promised, formatting).
- Several assertions are fine for one behavior.
- A test that is hard to write often signals mixed responsibilities or a hidden dependency: note it for the refactor, don't force it.
- Time is an input: inject clock and scheduler; never a real sleep to order events; await async outcomes with the stack's async assertion or the codebase's one wait helper.
- A red you cannot explain: reduce it to the smallest failing case before touching production code.
- Acceptance tests drive the application's use cases below the interface; the UI gets a thin smoke test.

Sources: tests and feedback — [Beck, *Extreme Programming Explained*](https://www.informit.com/store/extreme-programming-explained-embrace-change-9780201616415); readable tests — [Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests*, ch. 21](https://www.oreilly.com/library/view/growing-object-oriented-software/9780321574442/ch21.html).
