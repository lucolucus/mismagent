# SOLID — responsibilities and dependencies

**When:** responsibilities, substitutability, interfaces or dependencies obstruct the current change.

- **SRP** — separate independent reasons to change. Being one block does not by itself prove SRP.
- **OCP** — isolate the variations that are required or already demonstrated; no speculative extension points.
- **LSP** — an implementation preserves the contract's preconditions, results, errors and invariants. Contract tests give evidence for the cases they cover, not a proof.
- **ISP** — interfaces sized to their consumers' needs.
- **DIP** — policy does not depend on details; respect the deliberate architectural dependency graph.
- The Clean Architecture dependency rule is a distinct architectural concretization, not a synonym for DIP.
- No obligation of classes, inheritance, or an interface per implementation.
- A principle is a lens on a concrete obstacle, not a violation by itself: name the change it hinders.

Sources: [Martin, *Principles of OOD*](https://butunclebob.com/ArticleS.UncleBob.PrinciplesOfOod) and his note on [OCP as selective closure](https://blog.cleancoder.com/uncle-bob/2013/03/08/AnOpenAndClosedCase.html).
