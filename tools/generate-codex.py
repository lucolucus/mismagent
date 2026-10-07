#!/usr/bin/env python3
"""
generate-codex.py — derive the Codex/OpenAI packaging of mismAgent from the Claude Code plugin.

codex/ is a GENERATED view of plugins/mismagent: never edit it by hand — edit the plugin, then
re-run this script. The runtime-neutral part lives in derived.py.

Mapping (Codex: skills in .agents/skills, subagents as TOML in .codex/agents, AGENTS.md):
  plugin skill   skills/<n>/ (+ references/)  -> codex/skills/mismagent-<n>/   ($mismagent-<n>)
  command        commands/build.md + mm.py     -> codex/skills/mismagent-build/ (mm.py in scripts/)
  plugin agent   agents/<n>.md                 -> codex/agents/<n>.toml         (spawned by name)
  plugin README                                -> codex/AGENTS.md
  hooks                                        -> not shipped (Claude Code only)

Usage: python3 tools/generate-codex.py   [--out DIR]   (from the repo root; --out: tests)
"""
import json
import os
import re
import sys

from derived import (KERNEL, ROOT, adapt_common, agents_md_body, check_tree, emit_skill, fresh,
                     parse_frontmatter, plugin_agents, read, ship_mm, ship_skills, without_loop,
                     write)

OUT = os.path.join(ROOT, "codex")

GENERATED_NOTE = (
    "> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the\n"
    "> Claude Code plugin is the source of truth. Edit the source, then regenerate.\n"
)

# the adversary and the two guarantors of quality think harder; the builder works at medium
REASONING_EFFORT = {"mismagent-challenger": "high", "mismagent-reviewer": "high",
                    "mismagent-architect": "high"}


def adapt(text):
    """Claude Code idioms -> Codex idioms."""
    text = adapt_common(text)
    text = re.sub(r"/mismagent:([a-z0-9-]+)", r"$mismagent-\1", text)
    text = text.replace("$ARGUMENTS", "<the argument this skill was invoked with>")
    return text


BUILD_NOTES = """
## Codex execution notes (generated)
- **Dispatch = spawn the named subagent** from `.codex/agents/` (`mismagent-architect`,
  `mismagent-builder`, `mismagent-reviewer`) with the inputs the table names. Each spawn is a fresh,
  independent session: the fresh-context guarantee the reviewer relies on. You run in the main
  thread and wait for its last message (the agent's `RESULT`/`VERDICT`) before reporting.
- **No always-on mode here:** call `$mismagent-build` again for the next action.
- **No hooks here:** on Claude Code two hooks stop an agent from merging, tagging or moving state
  and from editing the human's files. On Codex the prompts say it and `mm check` verifies it.
"""


def convert_build():
    fm, body = parse_frontmatter(read(os.path.join(KERNEL, "commands", "build.md")))
    body = without_loop(body, "commands/build.md").rstrip() + "\n" + BUILD_NOTES
    emit_skill(OUT, adapt, GENERATED_NOTE, "build", fm.get("description", ""), body)
    ship_mm(OUT, adapt)


def toml_multiline(text):
    if "'''" in text:
        sys.exit("cannot TOML-encode (contains ''' literal): refusing to guess an escape")
    return "'''\n%s\n'''" % text


def convert_agents():
    for name in plugin_agents():
        fm, body = parse_frontmatter(read(os.path.join(KERNEL, "agents", name + ".md")))
        writes = any(t in fm.get("tools", "") for t in ("Bash", "Write", "Edit"))
        toml = (
            "# GENERATED from plugins/mismagent/agents/%s.md by tools/generate-codex.py — do not edit.\n"
            "name = %s\n"
            "description = %s\n"
            "sandbox_mode = %s\n"
            "model_reasoning_effort = %s\n"
            "developer_instructions = %s\n"
        ) % (name, json.dumps(name), json.dumps(adapt(fm.get("description", ""))),
             json.dumps("workspace-write" if writes else "read-only"),
             json.dumps(REASONING_EFFORT.get(name, "medium")), toml_multiline(adapt(body)))
        write(OUT, "agents/%s.toml" % name, toml)


LEGEND = """
> **Codex mapping (this packaging).** The commands are Codex **skills**: `$mismagent-explore`,
> `$mismagent-specify`, `$mismagent-build`, `$mismagent-conventions` (or `/skills`). The agents are
> Codex **subagents** in `.codex/agents/`, spawned by `$mismagent-build` and `$mismagent-explore`.
> The project's own conventions skill lives in `.agents/skills/conventions/`, and the project's
> settings (`## mismagent`: test, lint, smoke, thresholds) in this `AGENTS.md`. The Claude Code
> hooks are not shipped: the prompts and `mm check` hold their rules.

**Setup (once).** From the mismagent repo: `codex/install.sh <your-project-root>`. It copies the
skills into `<project>/.agents/skills/`, the subagents into `<project>/.codex/agents/`, and this
file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists: merge it), and
anchors every tool path to the absolute installed skills directory (re-run it after moving the
project). Requires Python 3 (standard library only) for `mm`. Verify: `/skills` lists
`mismagent-build`.
"""


def write_agents_md():
    write(OUT, "AGENTS.md", "# mismAgent — Codex packaging\n\n" + GENERATED_NOTE + LEGEND + "\n"
          + agents_md_body(adapt))


INSTALL_SH = """#!/bin/sh
# GENERATED by tools/generate-codex.py — installs the mismAgent Codex packaging into a project.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
[ -n "${1:-}" ] && [ -z "${2:-}" ] || { echo "usage: install.sh <project-root>" >&2; exit 2; }
mkdir -p "$1"
TARGET=$(cd "$1" && pwd)
SKILLS="$TARGET/.agents/skills"
# the path is written quoted into commands and inside the agents' TOML '''...''' strings
case "$SKILLS" in *'"'*|*'`'*|*'$'*|*'\\'*|*"'''"*) echo "install.sh: the path must not contain a double quote, backtick, dollar, backslash or '''" >&2; exit 2 ;; esac

mkdir -p "$SKILLS" "$TARGET/.codex/agents"
# the mismagent- names are this packaging's: replace them whole, so a retired piece goes too
rm -rf "$SKILLS"/mismagent-* "$TARGET"/.codex/agents/mismagent-*.toml
cp -R "$HERE"/skills/mismagent-* "$SKILLS/"
cp "$HERE"/agents/*.toml "$TARGET/.codex/agents/"

if [ -f "$TARGET/AGENTS.md" ]; then
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.mismagent.md"
  echo "AGENTS.md already exists -> wrote AGENTS.mismagent.md (merge it into yours)."
else
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.md"
fi
# anchor every path into the skills to this installation: absolute, so it works from any cwd
ESC=$(printf '%s' "$SKILLS" | sed 's/[|&\\]/\\&/g')
for f in "$SKILLS"/mismagent-*/SKILL.md "$SKILLS"/mismagent-*/references/*.md \\
         "$SKILLS"/mismagent-*/scripts/*.py "$TARGET"/.codex/agents/mismagent-*.toml \\
         "$TARGET/AGENTS.md" "$TARGET/AGENTS.mismagent.md"; do
  [ -f "$f" ] || continue
  sed "s|@@MISMAGENT_SKILLS@@|$ESC|g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
chmod +x "$SKILLS/mismagent-build/scripts/mm.py"
echo "mismAgent (Codex) installed into $TARGET — verify with /skills (expect mismagent-build)."
"""


def main():
    global OUT
    OUT = fresh(OUT, sys.argv, "generate-codex.py")
    print("generating codex/ from plugins/ ...")
    ship_skills(OUT, adapt, GENERATED_NOTE)
    convert_build()
    convert_agents()
    write_agents_md()
    write(OUT, "install.sh", INSTALL_SH, 0o755)
    check_tree(OUT, r"\$mismagent-([a-z0-9-]+)")
    print("done.")


if __name__ == "__main__":
    main()
