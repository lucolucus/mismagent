# The manifest schema and the block-file standard (NORMATIVE)

Read by `build-manifest` before writing or regenerating. `MM lint` and the worker-composer read
exactly these fields: anything a consumer needs that is not here **does not exist** — extend this
file first, then its readers.

## `building-blocks.yaml`

```yaml
blocks:
  - id: <slug>                  # unique
    type: aggregate | application-service | port | adapter | read-model | ui | scaffold
    context: <bounded-context>
    side: <side>                # from the profile
    wave: 0 | 1 | 2 …           # integer; 0 ONLY for scaffold; owners before consumers
    consumes: [<boundary-id>…]  # empty for owners/scaffold
    tests_nl: [<falsifiable AC in natural language>…]   # `by-construction` items marked as such
    related_adrs: [<NNNN>…]
    # per-type fields:
    invariants: [<INV-n rule>…]         # aggregate
    invariant_fields: [<field>…]        # aggregate — the confinement checks derive from these
    identity: <id strategy>             # aggregate
    tables: [<table>…]                  # aggregate
    commands: [<Command>…]              # application-service
    view_shape: { <field>: <type>… }    # read-model — every field has a source
    consumes_rm: [<read-model id>…]     # ui
    triggers: [<Command>…]              # ui
    model_hint: deep                    # OPTIONAL, any type; omit otherwise
    release: R0 | R1 | …                # REQUIRED except scaffold
    notes: "<explicit cut / where a prescribed surface went>"   # OPTIONAL
boundaries:                     # FIRST-CLASS section
  - id: <slug>
    owner: <block-id>           # aggregate | port | read-model — built before its consumers
    consumers: [<block-id>…]    # agrees both ways with the blocks' `consumes`
    projection: in-process | cross-deploy
    contract_form: openapi | event-schema       # cross-deploy ONLY
    pinned_types: { <Name>: <primitive or shared-kernel VO>… }  # every composite has its OWN row;
                                # a quantity's unit-vs-quantity granularity is explicit here
    keys: { <field>: "minted by <block-id> — <rule + stability>" }  # every id/correlation key
    contract_test: invariant-test | consumer-driven
    operation_ids: [<operationId>…]     # openapi ONLY — each resolves in the contract
    contract_path: <path>               # openapi ONLY — the file that holds them; a boundary an
                                        # earlier feature introduced keeps ITS file
    schema_paths: [<path>…]             # event-schema ONLY — may be a wave-0 scaffold output
    delivery: "<guarantee>"             # event-schema ONLY — e.g. "per-node in-order +
                                        # dedup(nodeId,seq) before the fold"
releases:                       # R0 first
  R0: { goal: "<what the user can do>", launch: "<what opens: screen / command>", blocks: [<id>…] }
build_order: [[<wave-0>…], [<owners>…], [<consumers>…]]   # derived
```

## The block files — `blocks/<context>/todo/<id>.md`

A **derived, status-less** rendering of one manifest row, so opening a block shows the whole block.

**Frontmatter** mirrors the row: `type`, `context`, `side`, `wave`, `consumes`, `related_adrs`,
`release`, `model_hint` (when set), plus the per-type fields (aggregate → `invariants`,
`invariant_fields`, `tables`; port → `projection`, `pinned_types`, `contract_test`; read-model →
`view_shape`). **No `status:` field, no `[ ]` checkboxes**: the state is the folder, moved only by
the worker-composer.

**Body:**
```
# <id> — <title>
## What to do     — what to build (from the model), 1–3 sentences
## Tasks          — the tests_nl / acceptance criteria, a plain list (read-only, not checkboxes)
## Dependencies   — the boundary owners it waits on, each seam inlined (below)
Sources: <related ADRs> · <tactical-model section>
```

## The per-type standard — the floor of detail

Hold every block to it at generation. `MM lint` checks the structural part: one file per row under `blocks/<context>/`, frontmatter
`type`/`context`/`wave` equal to the row (the other mirrored fields are not compared), no status;
for non-scaffold blocks only, non-empty `## What to do`, ≥ 1 `## Tasks` item, a `Sources:` line,
every `INV-n` and every `commands` entry named in `## Tasks`. The rest is **not linted** — you
guarantee it, and the composer's readiness and the reviewers judge it:

- **aggregate:** every invariant spelled out in the body and covered by ≥ 1 criterion;
- **application-service:** every command has ≥ 1 happy-path criterion **and** ≥ 1 rejection/failure
  criterion;
- **any block at a boundary:** every boundary it touches appears in `## Dependencies` with the
  **pinned signature inlined** — the Published-Language types, the `contract_test`, the `keys:`
  minting rules, and on a sync wire the `delivery:` guarantee. The reader never
  opens the YAML to learn the seam;
- **read-model:** the `view_shape` fields are reflected in ≥ 1 criterion;
- **ui:** the screen's states (empty / error / loading) are covered.

The ADR set a block reads is **derived** (`related_adrs` ∪ those of the boundaries it consumes ∪ those whose check names it as `from` —
`MM pack` resolves it), never a hand-compiled list. A gap found downstream bounces back to
`build-manifest`: regenerate, never hand-patch a block file.
