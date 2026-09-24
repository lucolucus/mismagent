---
name: mismagent-write-context-map
description: "mismAgent writer of the PROJECT context-map (<output_dir>/context-map.md): bounded contexts, relationships, ubiquitous language, open spikes. Amended across features, never re-forked. Invoked by mismagent-analyst."
---

> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the
> Claude Code plugin is the source of truth. Edit the source, then regenerate.

# mismAgent — Write Context Map

Write or amend `<output_dir>/context-map.md` — the **project's** strategic map. Invoked by
`mismagent-analyst`. Orientation: `methodology/mismagent.md`.

## Readers
- **Bounded contexts** → the manifest's boundaries.
- **Ubiquitous language** → the canonical names of blocks, operations, events and types; the
  verifier holds the diff to them.
- **Relationships** → each boundary's direction (architect).
- **Open spikes** → `type: spike` nodes (`write-task`); `central: true` ones run at wave 0.

An element with no reader is not written.

## Template
```markdown
# Context map — <project>

## Bounded context: <Name>
- **Role:** <core | supporting | generic> + <upstream | downstream | host of the view>
- **Ubiquitous language:** <Term = canonical meaning/values>
- **Introduced by:** <feature that first modeled this context>

## Relationships
- <ContextA> → <ContextB> : <upstream/downstream, conformist, ACL…> — <note>

## Open spikes
- [ ] <spike-slug>: <question> — <closure criterion> — side: <from the profile>
      — owner: <feature that raised it>   <!-- REQUIRED: tells a build its own spikes -->
      — central: <true|false>
```

## Rules
- Terms are **canonical and in the domain's language** (profile `ubiquitous_language.lang`): they
  become type and schema names — no synonyms, never translate a term the domain already uses.
- **Amend, never fork.** One map per project, in the `<output_dir>` root. Read it first; add the
  contexts, terms and relationships this feature introduces; never rewrite a context another feature
  modeled.
- **Renaming a canonical term is a breaking amendment:** only with the user, recorded as an ADR with
  the old → new mapping.
- The analyst writes the map; the explore/model conductor only closes an answered spike (`write-task`).
- No tactical detail here: that is `write-tactical-model`'s file.

## Outcome
Path, contexts added vs already present, key terms, open spikes, terms amended and why.
