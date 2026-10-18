# The review table

Seven dimensions, scored 1–5 on the code (a slice's diff, or the whole code at a release). A score
needs evidence: `file:line`. A **blocking** finding names the dimension, the rule of the standard it
breaks and the line; anything else is advice.

| dimension | 3 — acceptable, will decay | 4 — good | 5 — exemplary |
|---|---|---|---|
| **Simple design** (passes the tests · reveals intention · no duplication · fewest elements) | works, but long functions or constructors mix layout, wiring and logic | each function does one thing at one level; nothing speculative | reads like the domain; nothing to remove |
| **Naming and domain language** | domain words mostly, some `_dec`, `r[4]`, one word with two meanings | the glossary's words everywhere; no positional access | names make comments unnecessary |
| **Modularity and dependencies** | no cycles, but a module mixes concerns (domain + SQL + UI) or two modules write one table | layering as in `ARCHITECTURE.md`: domain free of UI and database; one owner per table | each module hides one decision; a change touches one module |
| **Duplication** | the same handler, query or setup repeated 3+ times | shared once in the right place; near-duplicates rare | once and only once |
| **Concision** | dead code, unused parameters or options, a layer with one user | nothing unused; no speculative generality | the smallest program that passes |
| **Error handling** | broad catches, swallowed errors, a missing lookup crashes with a type error | the error policy of `ARCHITECTURE.md`: typed domain errors, one boundary shows and logs | every failure has one obvious path, tested |
| **Test quality** | multi-behavior tests, tests poking widget internals, slow or order-dependent | one behavior each, named as the behavior, at the use-case seam, fast | tests read as the specification |

A slice passes when its diff scores **≥ 4 on every dimension it touches** and breaks no rule of
`ARCHITECTURE.md`. A release is healthy when the whole code scores ≥ 4 on every dimension; below
that, the architect runs a design pass.
