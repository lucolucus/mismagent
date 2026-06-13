# The build as *composition* — spec of the new build movement

> **Provenance:** distilled by walking through a real single-side build by hand (architecture
> ready, aggregates with invariants). This spec is kept **abstract** — it speaks of Aggregates,
> Ports and Application Services in general, naming no project; the **concrete derivation** (the
> per-block walk-through, the welding sequence on a real feature) lives **with the pilot project**,
> not in the portable core. **Purpose:** replace `dev-orchestrator-v2` (orchestrator) and revise
> `mism-developer-lean` (worker). **Status:** process PROTOTYPE — not yet in the core.
> **Vocabulary note:** this is v2, rewritten with the **established names** (DDD + Hexagonal +
> CQRS + contract testing) in place of the first draft's neologisms (slot/seam/seam-test).

---

## 0. In one sentence
The build does not **orchestrate**, it **composes**: it realizes the architecture's *building
blocks* and fits them together along the **boundaries** that `model` has already drawn, keeping
green both the blocks (on their own) and their **contract tests** (at the boundaries). The old
orchestrator was a *conductor* (sequencing, epics, producer-before-consumer, monopolist
git-writer); the new one is a *composer*.

---

## 1. The unit of work and the building blocks — with their real names

Not "files to touch", but the **standard bricks of the architecture**. Each has an established name:

| building block | established name (source) |
|----------------|---------------------------|
| root | **Aggregate / Aggregate Root** (tactical DDD) |
| command/use-case | **Application Service / Command Handler** (application layer, Clean/CQRS) |
| inter-context boundary | **Port** (Hexagonal, Ports & Adapters — Cockburn) |
| boundary impl. | **Adapter** (Hexagonal) |
| read view | **Read Model / Projection** (CQRS) |

**The default unit of work = an Application Service on an Aggregate.** The right size: one
behavior, a few ACs, one boundary. (The Aggregate-as-unit would be too big; see Open #1.)

---

## 2. The boundary (where the blocks fit together) — with the real names

Two kinds of boundary, both **already in the architecture** (not new artifacts to invent):

- **Intra-context = the Aggregate's boundary.** The aggregate *is* the consistency boundary, with a
  **single entry point** (the root). **The invariants live here, written once**; the Application
  Services pass through it, they do not rewrite them. (Pure DDD.)
- **Inter-context = the Bounded Context boundary**, realized by a **Port** /
  **Published Language** / **Anti-Corruption Layer**; in the **Context Map** it is the
  **Customer/Supplier** relationship (the consumer is the *customer*, the supplier is the
  *supplier* — as written in the context-map).

> The word "seam" (for "the point where you slip in a fake and replace the behavior") is from
> **Michael Feathers**, *Working Effectively with Legacy Code*: that's why the boundary tests run
> with a **fake Port**. The boundary is **not** nailed to HTTP: a Port *sometimes* projects into
> OpenAPI (when it crosses a deploy boundary, Open #4), but it doesn't have to.

---

## 3. The check on the seam = the **Contract Test** — with the real names

- **Inter-context:** a **Consumer-Driven Contract test** (Pact-style). It is *exactly* the "contract
  test" mismAgent **already had** — just no longer nailed to OpenAPI.
- **Intra-context:** the Aggregate's ordinary **invariant / unit tests**.

**What this is worth:** the "contract" mismAgent was obsessed with **is** the contract test on the
Bounded Context boundary. The redesign invents nothing: (1) it **generalizes** that contract test
beyond HTTP/OpenAPI (the boundary is a *Port*, which only *sometimes* projects into OpenAPI); (2) it
promotes the **Aggregate's boundary** (with its invariants) to equal standing — which the flow
previously ignored.

---

## 4. The WORKER (revised from `mism-developer-lean`)

The current worker is **good** and keeps almost everything (ONE block, self-review fix-loop until
green, strict return, no state, no straying across boundaries). **Four touch-ups:**

1. **It realizes ONE building block** (Aggregate / Application Service / Port / Adapter / Read
   Model), not a file-bag. Input = `{ block type, boundary it attaches to, ACs, architecture
   anchors, ADR enforced_by }`.
2. **The boundary is generalized:** a **Port** (interface), an **Aggregate**, a **schema** — not
   "`operationId` in the YAML + generated types". (Cross-side the Port projects into OpenAPI; the
   worker doesn't distinguish.)
3. **It does not duplicate the rule: it goes through the owner.** An Application Service passes
   through the **Aggregate root** that owns the invariant (a previous block), it does not rewrite
   it. "Green on its own" for the Application Service includes that the **Aggregate's invariant
   tests stay green**.
4. **The return names the block and the boundary honored**, not a `FILE_LIST`:
   `RESULT · BLOCK: <id> · BOUNDARY: <Aggregate|Port> · CONTRACT_TEST: green|n.a.`

---

## 5. The COMPOSER (revised from `dev-orchestrator-v2`)

**Two duties, nothing else:**
- **D1 — every block green on its own:** worker per block → profile gate + ADR `enforced_by` +
  the block's invariant/unit tests.
- **D2 — every boundary holds green:** it runs the **Contract Test** (CDC on the Port for inter;
  invariant tests on the Aggregate for intra). Red boundary = the composition fails → `BOUNCED`.

**A single ordering rule: boundary-before-consumer.** A block is built as soon as **its boundary
exists** (the interface), not when the other side exists:
- the **Aggregate** before its Application Services;
- the **Port** (interface) before the consumer and the Adapter — then consumer **∥** Adapter, in
  parallel, *against the interface* (it's the "generated types → parallel development" generalized).
Everything else runs in parallel. *The seam is everything, the order almost nothing.*

**What it is NO longer:** git-writer-monopolist *by ideology*; no epics, no
producer-before-consumer as dogma, no hand-written file DAG. **It reads the architecture**
(Context Map + tactical model + ADRs), not a `dag.yaml`.

**Algorithm (emerged from the walk-through §6):**
```
1. From the architecture derive the building blocks (Aggregate/App-Service/Port/Adapter/Read-Model)
   and the boundaries (Aggregate boundary intra; Bounded-Context boundary = Port inter), with their contract tests.
2. Build the boundary OWNERS first: the Aggregates (invariants+schema) and the Ports
   (the interface). They are the places where the rules / the boundaries live.
3. Build the CONSUMERS in PARALLEL (Application Service, Adapter, Read Model) against the
   existing boundaries. Each one: worker → D1 (green on its own, with a fake Port where needed).
4. When two blocks touch at a boundary → D2 (Contract Test with the REAL blocks on both sides).
5. DONE when: all blocks realized ∧ each one green on its own ∧ every boundary green (composed).
```
**State = the folder** (Agentheim inheritance), but the folders organize **building blocks**, not
file-tasks: the composer is the only one who moves them (plumbing, see Open #5).

---

## 6. The derivation — walked on a real feature (extracted)

This design was distilled by **walking a real single-side build by hand**, block by block: which
building blocks fall out, in what order, and what "green on its own" means for each. That
concrete walk-through — a per-block table and the welding sequence with real names — is
project-specific, so it lives **with the pilot project**, not in this portable core.

What that derivation established, and what the rest of this spec encodes:
- the boundary **owners** (Aggregate, Port) go first; the **consumers** (Application Service,
  Adapter) in parallel against them;
- the only ordering is **boundary-before-consumer**;
- the **moment of truth** is the consumer-driven Contract Test: that's where "the blocks compose by
  construction", and it is the single-side substitute for the HTTP contract test;
- an invariant lives **once** on its Aggregate root; the Port, the Read Model and the Application
  Services **ask** for it, they do not re-decide it (#16).

> The lean tasks an earlier `model` movement produced were already *almost* Application Services /
> Aggregates / Ports — confirmation that the model holds; what changes is *how the build consumes
> them* (building block + boundary, not file + references).

---

## 7. Open items — for review (re-read with the real names)

1. **RESOLVED → §9.** The Aggregate root is a **building block of its own, built first**; the order
   is not invented, it is *read from the architecture* (the architecture-discovery step / IDEA-2).
   Persistence = **a driven adapter of its own** (domain agnostic of technology).
2. **RESOLVED → §8.** How does the composer read the architecture, mechanically? A **building-block
   manifest** *generated* from the tactical model (not hand-written), which replaces the `dag.yaml`.
3. **RESOLVED → §9.** The Contract Test lives **with the boundary owner**: invariant tests
   in the **Aggregate** (intra); **consumer-driven** contract test **in the Port** (inter,
   consumer-owned), which the Adapter makes pass and the composer re-runs real-on-real in D2.
4. **RESOLVED → §8.** Boundary projection: `in-process` vs `cross-deploy`, chosen by
   `side(consumer) == side(supplier)`. Cross-deploy ⇒ the Port projects into OpenAPI + HTTP CDC.
   This is what makes it **truly generalize** (the old OpenAPI is just the cross-deploy projection).
5. **RESOLVED → §10.** git is plumbing, not identity: worktree = isolation (D1); **`git merge` = the
   composition**, and the Contract Test runs *on the merge* (D2); the composer owns the merges ⇒
   owns the state. Epics, universal producer-before-consumer, and `dag.yaml` all fall away.
6. **DECIDED (2026-06-09): `Composer`.** It names the intent (it composes the building blocks at the
   boundaries) and the philosophical contrast *composition vs orchestration*; the `-v2` disappears.
   (The worker remains to be renamed for consistency — minor.)
7. **Multi-model worker (IDEA-1).** The building-block spec could declare an `llm_tier`, and the
   composer could pick the worker's model per block (delicate Aggregate = powerful; trivial Adapter
   = cheap). Orthogonal: after the core is solid.
8. **OPEN (emerged from the comparison with Agentheim, §11): memory/prior-art for the worker.** The
   spec doesn't say **how the worker receives the "how"** (code conventions, prior-art of blocks
   already done, golden doc). Agentheim injects pre-loaded ADRs + prior-art + INDEX/knowledge;
   mismAgent the profile's `dev-architecture` skill. For the Composer the natural source is the
   **golden doc from IDEA-2** (injected memory) + the outcomes of blocks already `done` — to be made
   explicit.

---

## 8. The `model`→`build` bridge: the *building-block manifest* + the boundary projection (resolves #2 and #4)

### 8.1 The manifest is GENERATED from the tactical model, not hand-written
mismAgent principle: *"the contract is a consequence, not a source"*. Same for the manifest. The
`model` already has almost everything:

| source in `model` | → manifest row |
|-------------------|----------------|
| aggregate + invariants (tactical) | block `aggregate` (+ its intra Contract Test = the invariant tests) |
| command (+ actor) | block `application-service` |
| **Customer/Supplier** relationship (Context Map) | block `port` + block `adapter` + an inter **boundary** |
| domain event / read-model | block `read-model` |
| ADR `enforced_by` | mechanical constraint of the block |

So **`mism-build-dag` (or its successor) emits the manifest** in place of the file-task `dag.yaml`.
The manifest **is** the bridge: the only artifact the composer reads. No zombies — every row has
a downstream consumer (the composer itself).

> The manifest is the **product of the architecture-discovery step** (IDEA-2, see §9), not a
> separate artifact: that's where Aggregates/Ports/boundaries get chosen deliberately, and from
> those choices the manifest falls out.

### 8.2 Shape of the manifest (abstract)
```yaml
# building-blocks.yaml — generated from the tactical model
contexts: { <SupplierCtx>: {role: supporting}, <ConsumerCtx>: {role: core} }

blocks:
  - { id: <agg>,          type: aggregate,            context: <SupplierCtx>, side: <side>,
      invariants: [INV-…], persistence: <table>, exposes: agg:<agg> }
  - { id: <use-case>,     type: application-service,  context: <ConsumerCtx>, side: <side>,
      aggregate: <agg2>, consumes: [bc:<consumer>-><supplier>], invariants: [INV-…] }
  - { id: <read-port>,    type: port,    context: <ConsumerCtx>, side: <side>, exposes: bc:<consumer>-><supplier> }
  - { id: <read-adapter>, type: adapter, implements: <read-port>, context: <SupplierCtx>, side: <side> }

boundaries:
  - { id: agg:<agg>,                kind: aggregate,
      owner: <agg>,                 contract_test: invariants }
  - { id: bc:<consumer>-><supplier>, kind: bounded-context, relationship: customer-supplier,
      consumer: <ConsumerCtx>, supplier: <SupplierCtx>, port: <read-port>,
      contract_test: consumer-driven,
      projection: in-process }      # ← §8.3 decides in-process vs cross-deploy
```
The **only arc** is implicit and mechanical: *boundary-before-consumer*
(`consumes`/`aggregate`/`implements` ⇒ the boundary owner comes first). No hand-made DAG.
*(A filled-in instance with real names lives with the pilot project, alongside its derivation.)*

### 8.3 The boundary projection (resolves #4) — one line
```
boundary.projection = side(consumer) == side(supplier)  ?  in-process  :  cross-deploy
```
(`side` = deploy unit, from the profile)

- **`in-process`** (same side): the **Port is a code interface**; the Contract Test runs
  **in-process** (fake on one side for the consumer's "green on its own"; both real for the
  composition); the **Adapter** wires directly. → e.g. a single-side app where both contexts
  live in the one `app` side.
- **`cross-deploy`** (different sides): the **Port projects into OpenAPI** (operationId +
  **per-side generated types**); the Contract Test becomes **CDC** (the consumer publishes the
  expectations, the producer verifies them — Pact-style); the "Adapter" becomes an **HTTP
  client/server** + binding to the generated types. → e.g. a BE and a FE deployed independently.

**The same manifest `boundary`, two realizations**, chosen mechanically from the profile. Hence:

1. **mismAgent's old OpenAPI is the `cross-deploy` projection of a Bounded Context boundary.** The
   flow had nailed down *only* that one; now it is **one of two** → the redesign **generalizes**
   instead of working around (it resolves the #4/#11/#12/#13/#15 cluster at the root).
2. **BE‖FE is not a dogma, it's an effect.** In the `cross-deploy` case the blocks carry different
   `side`s and the composer dispatches workers per side ⇒ the BE‖FE parallelism **re-emerges as a
   consequence** of the projection, not as a hard-coded assumption. On single-side it doesn't show
   up (one side only). → resolves **#13** *conceptually*. ⚠️ But **operationally**, in the
   cross-deploy case it is identical to mismAgent (you still dispatch BE‖FE in parallel against the
   contract): a conceptual difference, not an operational one — adversarial check §12, attack 4.

### 8.4 What changes for `mism-build-dag`
It doesn't disappear, **its output mutates**: from `dag.yaml` (file-tasks) to
**`building-blocks.yaml`** (blocks + boundaries, with `projection`). It keeps: slice/release-tag (a
publishable block-set), the ACs on the blocks, the `enforced_by` ADRs. It loses: the per-file tasks
and the `references` the worker used to "skim".

---

## 9. Resolution of #1 + #3 — the boundary blocks and their contract tests (+ elevation of IDEA-2)

**Single rule (covers #1 and #3):** *the contract test lives with the block that owns the boundary,
and the boundary blocks come first.*
- **intra** boundary → owner = the **Aggregate root**: **a block of its own, built first** (#1);
  its contract test is the **invariant tests**, in there.
- **inter** boundary → owner = the **Port** (consumer-owned): **consumer-driven** contract test,
  lives **with the Port**; the Adapter makes it pass, the composer re-runs it real-on-real in D2 (#3).

**#1 — why root-first.** Parallelizing the consumers forces the boundary owner to exist first
(otherwise two Application Services would race to create the same root). But the order is not an
invented rule: it is **read from the architecture** (→ IDEA-2, below).

**Persistence = a driven adapter of its own (hypothesis A).** Reason: keep the Aggregate **pure
domain, agnostic of technology** — no SQLite/ORM in the core, invariants testable in milliseconds
without a DB, persistence swappable (in-memory ↔ SQLite) without touching domain or invariant tests.
On dual-nature invariants (e.g. INV-3 soft-delete): the **rule** lives on the Aggregate ("no
`Delete`"), the **mechanical guard** on the adapter (`enforced_by`: no `DELETE`) — just as the
architect already cut it in ADR-0004. The choice **does not move the contract tests**: it only gives
the guard its own separate "green on its own" (the persistence-adapter as a block).

**Elevation of IDEA-2 — architecture discovery is the front of the pipeline.** The manifest
(§8) is the **product** of the architecture-discovery step (IDEA-2, today embryonic in
`mism-architect`): that's where Aggregates/Ports/boundaries get chosen deliberately (pros/cons,
golden doc), and from those choices fall out blocks, boundaries, projections and the root-first
order. IDEA-2 stops being "an idea for review": it is the **first movement of the build**.
```
architecture discovery (IDEA-2: choices + golden doc)
   → building-block manifest (§8)
   → composer (§5): boundary owners first · consumers in parallel · contract tests at the boundaries
```

> ⚠️ **Caveat (§12, attack 3):** "invariants on the root, written once" is today a **principle**,
> not a **gate**. The old model didn't forbid it and a DDD dev puts them there anyway. It becomes a
> real *difference* only with a mechanical `enforced_by` — "no Application Service re-decides an
> Aggregate's rule". → **CLOSED in §14**: the gate confines invariant-bearing state inside the
> Aggregate (3 greps generated from the manifest), so re-deciding from outside is structurally
> impossible.

---

## 10. #5 — git as plumbing: `git merge` = the composition

The old orchestrator *was* "the only git-writer" (worktree, branch, merge, `git mv`): it was its
identity. In the new one, git is a **tool of the two duties**, re-derived:

- **worktree/branch per block = isolation** → it makes **D1** real (green on its own) and makes the
  parallelism safe (consumers writing at the same time don't step on each other). It survives, from
  *identity* to *tool*.
- **`git merge` = the composition itself.** A block that is green on its own gets **merged** into
  the integration line; as soon as a boundary has **both sides** in, the composer runs the
  **boundary's contract test on the merge result** = **D2**. Green → boundary welded, the merge
  stays. Red → composition failed → merge **rejected/`BOUNCED`**. *Composition isn't orchestrated,
  it's welded: it IS a merge gated by the contract test.*
- **The composer owns the merges ⇒ owns the state** (`git mv` between the block folders). It is not
  the "only git-writer" dogma: it is a **consequence** of being the integrator. The worker commits
  only code in its worktree — never merges, never state. (The old invariant, made precise: not "the
  only one writing git", but "**the only one doing merges and moving state**".)

**What falls away:** epics; producer-before-consumer as a universal merge rule (it survives *only*
as the CDC publish/verify in the cross-deploy projection, §8.3); the `dag.yaml`.
**What stays** (orthogonal safety): never merge/push onto the base branch without an explicit user
request (flow invariant #7).

---

## 11. Comparison with the ancestors (validation): Agentheim → mismAgent → Composer

> Sources: Agentheim = repo `github.com/heimeshoff/Agentheim` (skill `work` + agents, fetched
> 2026-06-09); mismAgent = `dev-orchestrator-v2.md` + `mism-developer-lean.md` of this repo.

| Dimension | **Agentheim** | **mismAgent** (`dev-orch-v2`+`dev-lean`) | **Composer** |
|---|---|---|---|
| Unit | task (file level) | lean task (files + `contract_ref`) | **Application Service on an Aggregate** |
| **Integration** | dependency-DAG + **per-file isolation** + per-task verifier — **no boundary** | same + **ONE** cross-side OpenAPI contract | **boundaries first-class** (Aggregate intra + Port inter), contract test per boundary, in-/cross-deploy projection |
| "Works by files" | **yes** (origin of the defect) | yes (inherited) | **no** (building block + boundary) |
| Invariants | no home (ACs per task) | ACs per task | **on the Aggregate root**, once |
| Who commits | the orchestrator | the worker (story branch) | the worker (worktree) |
| Who moves the state | **the worker** | the orchestrator (`git mv`) | the Composer |
| Who writes the ADRs | **the worker** | upstream (model) | upstream (IDEA-2) |
| Merging | commit/task after the verifier | merge to master, produces-before-consumes | **`git merge` = composition**, contract test on the merge |
| Parallelism | DAG + file-isolation | **hard-coded BE‖FE** + DAG | **effect** of the cross-deploy projection |
| Memory for the worker | pre-loaded ADRs + prior-art + INDEX/knowledge | dev-architecture skill | *gap → Open #8* |

**Four outcomes (they validate the spec):**
1. **The "works by files" is ANCESTRAL.** Agentheim integrates only at the file level (BCs
   "separated only by README + index"). mismAgent inherited it and bolted on *one* cross-side
   contract. The Composer is the **first** to replace per-file isolation with architectural
   boundaries. *The leap is in the integration, not in the worker — but it is **evolution**, not
   revolution (§12), and the per-file isolation being abandoned was also a robustness (§12,
   attack 2).*
2. **The worker is nearly unchanged along the lineage** (and mismAgent had already slimmed it down
   from Agentheim: removed ADRs/state/README, added the commit). The Composer keeps the worker lean
   and changes only *what it produces* (a building block) and *how it integrates*. → the worker
   resembles Agentheim's because **it descends from it**; but the integration model is another.
3. **mismAgent already had ~80% of the cross-deploy:** `dev-orch-v2` already has "additive vs
   breaking → producer-before-consumer *only at merge* (the FE has the generated types)". The
   Composer doesn't invent it: it **generalizes** it (one projection among several) and pairs it
   with the intra-Aggregate boundary. → coherent evolution, not a break.
4. **Gap surfaced → Open #8:** the **memory/prior-art for the worker** (Agentheim injects it
   heavily; the Composer spec doesn't). Natural source: the IDEA-2 golden doc + the outcomes of
   `done` blocks.

**What of the old `dev-orchestrator-v2` SURVIVES in the Composer:** state = the folder, sole
merger/state-mover, fresh-context verifier + code-review, worktrees for isolation,
no-merge-onto-base-without-OK. **What FALLS:** the file-task `dag.yaml` (→ manifest), BE‖FE as a
hard-coded axis (→ effect of the projection), universal producer-before-consumer (→ only the
cross-deploy CDC), epics/`project-orchestrator`.

---

## 12. Adversarial check (fresh-context challenger) — verdict: **RESHAPE, not PROCEED**

> An attack on the claimed differences (§8/§9/§11). Outcome: they are **real but narrower** than
> presented; two claims are rhetorical/unproven. Before going into the core the spec must *prove*
> what it currently *asserts*.

**Attacks that hold:**
1. **Unbalanced comparison.** An idealized, **never executed** spec vs real systems. Manifest (#2),
   worker memory (#8), projection: **not built**. The "differences" are hypotheses, not facts.
2. **Per-file isolation is also robustness** (zero conflicts guaranteed, no dependency on a perfect
   upstream architecture). The boundary model is **fragile** if IDEA-2 gets a boundary wrong/misses
   one — more likely on **greenfield** (`dev_architecture: none`), i.e. exactly where mismAgent
   already struggles. The Composer is riskier *precisely there*.
3. **"Invariants on the root" is a principle, not a gate.** The spec doesn't prevent an Application
   Service from re-implementing an invariant: without a mechanical check, it's "write good code",
   same as before.
4. **"BE‖FE is an effect" is rhetoric.** In the cross-deploy case you still dispatch BE‖FE in
   parallel against the contract → operationally **identical** to mismAgent. No operational
   difference.
5. **Weak/circular evidence.** The only datum (the .NET prototype) was written **by hand** (not by
   the process, which doesn't exist), **a single in-process vertical**, with the spec **derived-from
   and validated-against the same case**. It only proves a human can write good DDD for one
   vertical.

**The underlying attack:** the Composer is newest/most valuable in the **multi-team cross-deploy**
case (where mismAgent already worked) and more **ceremonious/risky in the single-side greenfield**
— which is the very *trigger* of the redesign ("too heavy for single-side"). It risks **solving the
wrong problem**: the benefit lands where the pain wasn't, the ceremony where it was.

> **Reply (the user) — DOWNGRADES this attack.** Category error: the boundary work
> (port + contract test) is **the worker's work**, not Composer ceremony (the Composer stays thin,
> 2 duties). The worker is **specializable via skills** (precedent: the per-side
> `dev-architecture`). The **projection (#4) selects the worker's skill**: single-side → a light
> "in-process boundary" skill (interface + in-process test = what you'd write anyway); cross-deploy
> → a heavy "OpenAPI/CDC" skill. The weight **scales with the case, at the worker level**. This
> **unifies #8 (memory), IDEA-1 (model tier) and #4 (projection)** into a single lever: *the worker
> specialized per (block-type × projection)*. → (a) it is not existential: it is "design the
> worker's skill matrix". **What it does NOT solve:** attack 2 (a skill doesn't save a wrong
> architecture: a wrong boundary in IDEA-2 ⇒ broken composition, without the per-file-isolation
> fallback) and condition (b) (the invariant gate). Cost reallocated: those skills must be
> **written**.

**What survives (under conditions):**
- the **intra-Aggregate boundary** as the single home of the invariant — absent in *both* ancestors
  — **but** only with a mechanical gate (which is missing);
- **one methodology for single- and multi-side** under a single boundary concept — real, **but** the
  single-side value is yet to be proven (and could be negative).

**RESHAPE → PROCEED conditions (before the core):**
- **(a) ~~existential~~ → DOWNGRADED to a design task (reply above):** the single-side weight is
  the **skill-specialized worker's** work (projection → skill: light in-process / heavy
  cross-deploy), not Composer ceremony. What remains is to **design the worker's skill matrix**
  (block-type × projection), which absorbs #8 + IDEA-1 + #4.
- **(b) RESOLVED (design) → §14:** the mechanical gate = **confining invariant-bearing state inside
  the Aggregate** (3 greps generated from the manifest: no persistence/state writes from outside, no
  re-deciding from raw reads). ADR-0003/0004 are already instances of it. *(Designed, not built.)*
- **(c)** inflated claims already degraded: #13 "BE‖FE as effect" rhetorical (§8.3), "revolution" →
  "evolution" (§11). *(Done.)*
- **(d) residual risk (attack 2, NOT closed):** fragility on greenfield — a skill doesn't save a
  wrong architecture; a wrong/missing boundary in IDEA-2 breaks the composition without the
  per-file-isolation fallback. To be guarded (perhaps: a more robust IDEA-2, or a fallback).

---

## 13. The worker's skill matrix (absorbs #4 + #8 + IDEA-1)

**Principle:** **one single worker**, which *loads the right skills for each block* (just as today
it loads the per-side `dev-architecture`). Each invocation composes:
**(1 block-type) + (1 projection, if it touches a boundary) + (per-side memory) + (model tier)**.
All the specialization lives **in the skills**; the Composer stays thin.

### A — skills per BLOCK-TYPE (core, portable)
| skill | realizes | carries with it |
|-------|----------|-----------------|
| `realize-aggregate` | Aggregate root + value objects | **invariants + invariant-tests** (owns the rule) |
| `realize-application-service` | thin command/use-case | AC tests; leans on root+port, does **not** duplicate the rule |
| `realize-port` | consumer-owned read-only interface (declaration of the boundary) | the spec of the consumer-driven contract test |
| `realize-adapter` | impl. of a port — variants: *read* (toward another context) and *persistence* (repository) | round-trip tests; honors `enforced_by` |
| `realize-read-model` | query/projection (CQRS) | the view's test |

### B — skills per boundary PROJECTION (core) — selected by #4
| skill | boundary | weight |
|-------|----------|--------|
| `seam-in-process` | code interface + in-process contract test (fake on one side) | **light** (single-side: "interface + test", nothing else) |
| `seam-cross-deploy` | OpenAPI from the port + per-side types + **CDC** publish/verify (Pact) | heavy (multi-side) |

### C — cross-cutting (core)
- `tdd` (red-green-refactor) — **already exists in Agentheim**; the A skills lean on it.
- *(self-review/fix-loop until the gate is green = the worker's **process**, not a skill.)*

### D — PER-SIDE / PER-STACK memory (provided by the project = #8, produced by IDEA-2) — NOT core
- `<side>-dev-architecture` — golden doc: conventions, layering, naming, test framework. *(Origin-project precedents: `be-dev-architecture`, `fe-dev-architecture`)*
- `<stack>-persistence` — DB strategy: schema, migrations, backups.
- `git-branching` — branch/commit conventions. *(already exists)*

### Non-skill, dispatch parameter
- **model tier** (IDEA-1): high for a delicate `realize-aggregate`, low for a trivial `realize-adapter`.

### Synthesis
- **One invocation = A(block) [+ B(projection) if boundary] + D(per-side memory) + tier.** That's
  the matrix.
- **It absorbs three open items:** #4 → the **B** skills; #8 → the **D** skills; IDEA-1 → the tier.
- **Net-new to write = only A + B (7 core skills)**; **C** exists, **D** is produced by IDEA-2.
  Every A/B skill is *thin* (one pattern). `seam-in-process` **is the proof that single-side is not
  ceremony**.
- **Open items #7/#8 → closed in here** (absorbed into the matrix). The only concrete remainder is
  gate (b) of §12 → §14.

---

## 14. The invariant gate — "invariants on the root" becomes mechanical (closes (b))

You cannot grep for *"this code duplicates a business rule"*. So the gate **does not look for the
duplication**: it closes the **negative space** — *the state that embodies an invariant is touched
ONLY inside the Aggregate*. If no one outside can touch it, no one outside can re-decide it.

**Three grep-able rules per Aggregate** (generated from the §8 manifest, executed by the verifier):
1. **No persistence writes from outside:** no `INSERT/UPDATE/DELETE` on the Aggregate's tables
   outside its persistence-adapter. *(generalizes ADR-0002/0004)*
2. **No state writes from outside:** the root's invariant-bearing properties are
   `private set`/init-only; no Application Service assigns its fields ⇒ the only way to mutate is a
   method of the root, where the invariant lives.
3. **No re-deciding from raw reads:** the invariant-bearing fields (e.g. `Active`) are referenced
   only inside the Aggregate; consumers use the named predicate
   (`Sellable`/`port.Sellable`), not `Active == true`. ⇒ grep: `\.Active` outside the aggregate =
   violation.

1+2 confine the **mutation**, 3 the **re-decision on read**. Together: the invariant is structurally
captive of the root.

**Generated from the manifest:** every Aggregate already declares `invariants`; we add
`invariant_fields` + `tables`, and the gate **generates** the three `enforced_by` greps. The
verifier runs them. → closes the loop with #2.

**Real ADRs are already instances of this** (the pilot project has them): an ADR "no `DELETE` on
the aggregate's table" = rule 1; an ADR "no `UPDATE` on a write-once field" = rule 1 (write-once);
an invariant-bearing field confined to its aggregate = rule 3. (b) **generalizes** them to every
Aggregate.

**Honest limit:** it proves "state confined", not "single rule" semantically. A parallel predicate
that doesn't touch the confined fields (e.g. a magic number) is caught by the **code-review**
(discursive ADR), not by the verifier. The gate closes the **structural** case (the bulk); the
semantic one remains with the review.

---

## 15. The Composer's execution flow (ties §5 · §8 · §10 · §13 · §14 together)

Designed with the user on 2026-06-09. A **deterministic** flow (loop + parallel + barrier) → it is
the shape the core's `Composer` command would encode.

```
INPUT: building-block manifest (from IDEA-2) + profile (sides, gate, branching)

Phase 0 · INGEST
  blocks, boundaries (with projection §8.3 + PINNED TYPES), profile
  graph = ONLY "boundary-before-consumer" edges; state = folders blocks/<context>/{todo,doing,done}

Phase 1 · READINESS (model→build gate, evolved)
  ∀ block: complete spec · ∀ boundary: PINNED TYPES + contract_test defined + projection chosen · executable gate
  ✗ → BOUNCE to IDEA-2 (incomplete manifest), don't start          ← Wave-1 lesson (see §16-proto)

Phase 2 · WAVE LOOP (until all done)
  ready = blocks whose consumed boundaries' OWNERS are in done      (owners first, §5)
  parallel (cap N, worktree per block):
     skills = select(block.type × projection) + dev-architecture(side) + tier   (§13)
     worker.realize(block_spec, skills, boundary-interfaces)   # TDD → green on its own
     return: READY | BOUNCED | BLOCKED

  Phase 3 · D1 — GREEN ON ITS OWN (for each READY)
     fresh-context verifier: build + tests + enforced_by(§14) + ACs covered → PASS = eligible for merge

  Phase 4 · COMPOSE
     the Composer does `git merge` of the block into the integration line        (merge = composition, §10)

  Phase 5 · D2 — WELD THE BOUNDARY (for each boundary with BOTH sides now merged — BARRIER)
     run the boundary's contract_test, real-on-real
     GREEN → boundary WELDED; involved blocks → done
     RED   → BOUNCE the consumer (composition failed)

Phase 6 · RELEASE
  slice green ⇔ all its blocks in done ∧ all its boundaries welded → tag → feature-flag
  ⟵ HERE the user confirms (build = you delegate, you confirm only at the end)

Phase 7 · REPORT
```

**Bounce (where the flow goes back):**
- under-specified boundary (Phase 1, or discovered in Phase 5) → **to IDEA-2** (pin the Published
  Language) → re-run;
- worker `BOUNCED` (ambiguous AC) → to the manifest/spec; · D1 FAIL / D2 RED → to the worker
  (rework, max K cycles).

**Who touches what:** only the Composer merges and moves the folders; the workers write code in the
worktrees, never state, never merges (§10).

*(A worked run of this flow on a real feature — the actual waves, merges and D2 — lives with the
pilot project's derivation, not in this portable core.)*

**Two things the design pins down:**
1. **Phase 1 checks that the boundary types are pinned**: Wave-1 would have been stopped here,
   before wasting the workers → the finding becomes a **readiness rule**.
2. **Where the user stands:** upstream in **IDEA-2** (architecture/stack/boundaries) and downstream
   at **Phase 6** (confirming the release). In between, they delegate.

---

## 16. The user's natural-language tests → translated by the worker (the user's idea, 2026-06-09)

Whoever designs the blocks (IDEA-2 / the manifest author) can **ask the user, in natural language,
what tests they would want** on a block or a boundary. Those sentences become the **source of
intent** that the worker translates into the formal test.

- In the manifest, a block/boundary carries `tests_nl: [...]` — the user's sentences, e.g. *"if I
  change a master value, past records keep the value they had"*, *"I can't use a deactivated item"*,
  *"two items can't share the same name"*.
- The worker (`realize-aggregate`/`realize-port`/…) **translates** `tests_nl` → the formal test
  (invariant-test on the root · consumer-driven contract-test on the port). The formal test is the
  **encoding** of the user's wish, **not** an invention of the worker.
- **Why it matters:** (1) the tests are **intent-authored by the user** (the domain-owner) and
  encoded by the machine — it's the consumer-driven contract in its purest form; (2) it keeps the
  user **at high presence on the *what must hold***, not on the *how*; (3) it captures implicit
  rules and edge cases the tactical model doesn't have. (The Gherkin ACs of the old tasks were
  already a semi-formal version of this: `tests_nl` is their natural-language upstream.)
- **In Phase 1 (readiness):** high-value blocks/boundaries should carry `tests_nl`; a boundary
  **without** the user's test intent is a bounce candidate — *"ask the user what they want to test
  here"*.
