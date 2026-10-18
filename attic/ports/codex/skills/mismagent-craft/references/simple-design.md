# Simple design — judging the green

**When:** on green, deciding whether the change needs simplifying.

Four rules, in priority order:
1. **Passes the tests.**
2. **Reveals intention** — a reader understands what it does and why.
3. **No duplication** — of knowledge.
4. **Fewest elements** — remove what serves none of the above.

This is Fowler's wording and order; Beck's own formulation, quoted on the same page, swaps rules 2 and 3. Read them as tensions to balance, not a strict sort.

- Duplication means mainly the same decision kept in more than one place; syntactic resemblance alone does not demand an abstraction.
- Minimize elements only while understandability and contracts hold.
- Judge the current change only; no quest for the perfect architecture.
- Name the concrete obstacle you found (which rule, where): that is what the refactor removes, with `clean-code.md`, `solid.md` or `refactoring.md`. None found → the step ends with no change.

Source: Beck, *Extreme Programming Explained*, 1st ed., p. 57, as documented by [Fowler, *BeckDesignRules*](https://www.martinfowler.com/bliki/BeckDesignRules.html).
