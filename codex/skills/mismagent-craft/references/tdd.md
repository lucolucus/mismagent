# TDD — the next test

**When:** choosing the next test, diagnosing a red, judging a brittle or unreadable test.

- Turn one required behavior (an acceptance criterion, an invariant, a `tests_nl` line) into one concrete example.
- Watch it fail **for the expected reason**: a compile error or a broken fixture is not yet the red you want.
- Make it pass with the minimum; restructure only on green.
- Name, arrangement, action and outcome make the verified behavior evident: essential fixtures only, diagnostic assertions (a failure says what broke).
- Assert results and contractual interactions, not incidental details (private calls, an order nobody promised, formatting).
- Several assertions are fine when they describe one behavior.
- A test that is hard to write often signals mixed responsibilities or a hidden dependency: note it for the refactor step instead of forcing the test.
- A red you cannot explain: reduce it to the smallest failing case before changing production code.
- Block-specific evidence (invariants, contracts, contention, rendering) belongs to the block-type skill; don't redo it here.

Sources: tests and feedback — [Beck, *Extreme Programming Explained*](https://www.informit.com/store/extreme-programming-explained-embrace-change-9780201616415); readable tests — [Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests*, ch. 21](https://www.oreilly.com/library/view/growing-object-oriented-software/9780321574442/ch21.html).
