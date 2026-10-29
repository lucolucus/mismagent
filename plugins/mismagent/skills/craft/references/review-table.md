# The review table

Seven dimensions, a checklist on the code (a slice's diff, or the whole code at a release): each
one checked — nothing found, or findings. No scores: a finding carries its evidence, `file:line`. A
**blocking** finding names the dimension, the rule of the standard it breaks, the line and what
would fix it; anything else is advice.

| dimension | a finding — the code will decay | good |
|---|---|---|
| **Simple design** (passes the tests · reveals intention · no duplication · fewest elements) | long functions or constructors mix layout, wiring and logic | each function does one thing at one level; nothing speculative |
| **Naming and domain language** | `_dec`, `r[4]`, one word with two meanings | the glossary's words everywhere; no positional access |
| **Modularity and dependencies** | a cycle, a module that mixes concerns (domain + SQL + UI), two modules that write one table | layering as in `ARCHITECTURE.md`: domain free of UI and database; one owner per table |
| **Duplication** | the same handler, query or setup repeated 3+ times | shared once in the right place; near-duplicates rare |
| **Concision** | dead code, unused parameters or options, a layer with one user | nothing unused; no speculative generality |
| **Error handling** | broad catches, swallowed errors, a missing lookup crashes with a type error | the error policy of `ARCHITECTURE.md`: typed domain errors, one boundary shows and logs |
| **Test quality** | multi-behavior tests, tests poking widget internals, slow or order-dependent | one behavior each, named as the behavior, at the use-case seam, fast |

Always, under every dimension: SOLID, YAGNI, DRY, test first (the `craft` skill), and the project's
conventions as decided.

A slice passes when its diff brings **no blocking finding on a dimension it touches** and breaks no
rule of `ARCHITECTURE.md`. A release is healthy when the whole code has no blocking finding of the
table; otherwise the architect runs a design pass.
