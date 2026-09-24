# The manifest schema and the block-file standard (NORMATIVE)

Read by `build-manifest`. `MM lint` and the worker-composer read
exactly these fields: anything a consumer needs that is not here **does not exist** — extend this
file first, then its readers.

## `building-blocks.yaml`

```yaml
blocks:
  - id: <slug>                  # unique
    type: aggregate | application-service | port | adapter | read-model | ui | scaffold
    context: <bounded-context>  # infrastructure serving several contexts: its declared host context
    side: <side>                # from the profile
    wave: 0 | 1 | 2 …           # integer; 0 ONLY for scaffold; owners before consumers
    what: "<1–3 sentences: what to build, from the model>"   # non-scaffold
    sources: [<tactical-model section>, <ADR NNNN>…]         # non-scaffold
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
    after: [<block-id>…]                # OPTIONAL: waits for these to be integrated
    release: R0 | R1 | …                # REQUIRED except scaffold
    notes: "<explicit cut / where a prescribed surface went>"   # OPTIONAL
boundaries:                     # FIRST-CLASS section
  - id: <slug>
    owner: <block-id>           # any ordinary block that publishes it — built before its consumers
    consumers: [<block-id>…]    # agrees both ways with the blocks' `consumes`
    pinned_types: { <Name>: <primitive or shared-kernel VO>… }  # every composite has its OWN row;
                                # a quantity's unit-vs-quantity granularity is explicit here
    keys: { <field>: "minted by <block-id> — <rule + stability>" }  # every id/correlation key
    contract_test: invariant-test | consumer-driven
releases:                       # R0 first
  R0: { goal: "<what the user can do>", launch: "<what opens: screen / command>", blocks: [<id>…] }
```

## The block files — `blocks/<context>/todo/<id>.md`

**Rendered by `MM manifest render F`** from the row — never written or patched by hand: a
status-less projection (frontmatter mirroring the row; `## What to do` ← `what`, `## Invariants`, `## Tasks` ←
`tests_nl`, `## Dependencies` ← the touched boundaries with their pins, `Sources:` ← `sources`), so
opening a block shows the whole block. The state is the folder, moved only by the worker-composer.

## The per-type standard — the floor of detail

Hold every row to it. `MM lint` checks the structural part (the list: the plugin's `tools/CLI.md`) — e.g. every `INV-n`
and every `commands` entry named in the rendered `## Tasks`, so the `tests_nl` name them. The rest
is **not linted** — you guarantee it, and the composer's readiness and the reviewers judge it:

- **aggregate:** every invariant spelled out in `invariants` and covered by ≥ 1 criterion;
- **application-service:** every command has ≥ 1 happy-path criterion **and** ≥ 1 rejection/failure
  criterion;
- **any block at a boundary:** its boundaries' `pinned_types`, `contract_test` and `keys:` complete
  enough that the rendered `## Dependencies` alone teaches the seam; order/duplicate guarantees come
  with the owner's ADR in the pack;
- **read-model:** the `view_shape` fields are reflected in ≥ 1 criterion;
- **ui:** the screen's states (empty / error / loading) are covered;
- **scaffold:** no domain — no boundary, invariant or owned shared type (lint refuses them).

The ADR set a block reads is **derived** (`related_adrs` ∪ those of the owners of the boundaries it consumes ∪ those whose check names it as `from` —
`MM pack` resolves it), never a hand-compiled list. A gap found downstream bounces back to
`build-manifest`: fix the YAML and re-render.
