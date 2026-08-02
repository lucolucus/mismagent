---
name: mismagent-write-context-map
description: "mismAgent''s specialized context-map writer (explore movement). Produces the PROJECT-level strategic map <output_dir>/context-map.md: bounded contexts (DDD strategic) + relationships + ubiquitous language per context + list of open spikes. It is the project''s TRUNK, shared by every feature and AMENDED across them \u2014 never re-forked (a second context-map would fork the canonical names). The per-feature TACTICAL level lives elsewhere: features/<feature>/tactical-model.md (write-tactical-model). Invoked by mismagent-analyst (inside explore). Every element has a downstream consumer (survival test), so it is not a zombie."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# MismAgent — Write Context Map (writer, explore)

Write/update `<output_dir>/context-map.md` — the **project's** strategic map, not the feature's.
Invoked by `mismagent-analyst`. Orientation: `methodology/mismagent.md`.

## Why it exists (downstream consumers = survival test)
- **Bounded contexts** → seed the **boundaries** (manifest boundaries, `build-manifest`).
- **Ubiquitous language** → seeds the **canonical names** of blocks and types (and, if a boundary
  projects cross-deploy, of the OpenAPI `components/schemas`); the `mismagent-verifier` greps those
  terms on the diff → drift = FAIL.
- **Relationships** → decide each boundary's direction and its projection (architect).
- **Open spikes** → become **`type: spike` nodes** (via `write-task`).

If an element has no consumer, **do not write it**.

## Template
```markdown
# Context map — <project>

## Bounded context: <Name>            <!-- from the profile; e.g. Maintenance (e.g.) -->
- **Role:** <core | supporting | generic> + <host of the view | upstream | downstream>
- **Ubiquitous language:** <Term = canonical values/meaning>   → schema name (verifier grep)
- **Introduced by:** <feature that first modeled this context>

## Relationships
- <ContextA> → <ContextB> : <type: upstream/downstream, conformist, ACL...> — <note>

## Open spikes (unknowns/risks → future spike nodes)
- [ ] <spike-slug>: <question to answer> — <closure criterion> — expected side: <from the profile>
      — owner: <the feature that raised it>   <!-- REQUIRED: the map is project-wide, so a build
           run must be able to tell its own spikes from another feature's -->
```

## Rules
- The ubiquitous-language terms are **canonical and in the domain language** — the language is
  declared by the profile (`ubiquitous_language.lang`); default: the language the domain speaks
  (e.g. an Italian-domain project keeps `TipoIntervento`, `StatoOcr`). They will become schema/type
  names: no scattered synonyms, **never** translate a term the domain already uses.
- Reuse the **domain's bounded contexts declared in the profile** as reference (e.g. a
  context like `Maintenance` (e.g.)).
- **Project scope — amend, never fork.** One context map per project, in the `<output_dir>` root.
  On a second feature you **read the existing file first** and *extend* it: add the contexts the
  feature introduces, add terms to the contexts it touches, add relationships. **Never** rewrite a
  context another feature already modeled, and never create a second map: two maps fork the
  ubiquitous language, and the canonical names are exactly what everything downstream inherits.
  *(This reverses the old per-feature rule — see the v0.13.0 layout note in `methodology/mismagent.md`.)*
- **Renaming a canonical term is a breaking amendment**: it invalidates the verifier's greps on
  already-merged blocks. Do it only with the user, and record it as an ADR
  (`<output_dir>/decisions/`) with the old → new mapping.
- Spikes are **actionable** (question + closure criterion), not vague notes.
- **No tactical here.** Aggregates, invariants, domain events and commands belong to the feature:
  `write-tactical-model` → `<output_dir>/features/<feature>/tactical-model.md`.

## Outcome
Path of the file, bounded contexts **added vs already present**, key ubiquitous-language terms,
open spikes (materializable as `type: spike` nodes via `write-task`), and — if any — the terms
amended and why.
