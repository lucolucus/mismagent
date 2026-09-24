# Frugality — reuse, native, dependency, abstraction

**When:** choosing between reuse, a native capability, a dependency or a new abstraction.

Climb down; stop at the first adequate rung, weighing clarity and maintenance:
1. **YAGNI** — does an acceptance criterion, an invariant or a `tests_nl` line require it now? If nothing mandates it, don't build it: no speculative abstraction.
2. **Its owner already has it** — the root's method or predicate, an existing value object, a shared-kernel type. Don't duplicate the rule.
3. **Native** — a persistence constraint, a standard-library or framework feature, the framework's observable state, over a hand-roll.
4. **An installed dependency** — reuse what is there.
5. **The minimum that works** — only now, and the smallest of it.

- A new dependency or generalization needs a concrete need; weigh its cost (maintenance, security surface, size) against the code it saves.
- Deletion beats addition; the boring solution beats the clever one.
- Frugality never touches: boundaries, invariants, ADR checks, tests, code rules, input validation, error handling that prevents data loss, security.
- YAGNI never justifies skipping tests or maintainability.

Source: [Fowler, *Yagni*](https://martinfowler.com/bliki/Yagni.html).
