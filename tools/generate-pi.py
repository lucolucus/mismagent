#!/usr/bin/env python3
"""
generate-pi.py — derive the pi (pi.dev) packaging of mismAgent from the Claude Code plugin.

pi/ is a GENERATED view of plugins/mismagent: never edit it by hand — edit the plugin, then
re-run this script. The runtime-neutral part lives in derived.py.

Mapping (pi: skills in .agents/skills, prompt templates in .pi/prompts, the subagent example
extension's agents in .pi/agents, AGENTS.md):
  plugin skill   skills/<n>/ (+ references/)  -> pi/skills/mismagent-<n>/    (/skill:mismagent-<n>)
  command        commands/build.md + mm.py     -> pi/skills/mismagent-build/ (mm.py in scripts/)
                                                + pi/prompts/mismagent-build.md (/mismagent-build,
                                                  pi substitutes $ARGUMENTS in prompt templates)
  plugin agent   agents/<n>.md                 -> pi/agents/<n>.md
  plugin README                                -> pi/AGENTS.md
  plugin.json    version                       -> pi/package.json (`pi install` alternative)
  hooks                                        -> not shipped (Claude Code only)

Usage: python3 tools/generate-pi.py   [--out DIR]   (from the repo root; --out: tests)
"""
import json
import os
import re
import sys

from derived import (KERNEL, ROOT, SKILLS, adapt_common, agents_md_body, check_tree, emit_skill,
                     fresh, parse_frontmatter, plugin_agents, read, ship_mm, ship_skills,
                     version, without_loop, write)

OUT = os.path.join(ROOT, "pi")
PROMPTS = ("build",)  # commands the human types: prompt templates beside their skill

GENERATED_NOTE = (
    "> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the\n"
    "> Claude Code plugin is the source of truth. Edit the source, then regenerate.\n"
)


def adapt(text):
    """Claude Code idioms -> pi idioms."""
    text = adapt_common(text)
    text = re.sub(r"/mismagent:([a-z0-9-]+)",
                  lambda m: ("/mismagent-%s" if m.group(1) in PROMPTS else "/skill:mismagent-%s")
                  % m.group(1), text)
    return text.replace("$ARGUMENTS", "<the argument this skill was invoked with>")


BUILD_NOTES = """
## pi execution notes (generated)
- **Dispatch = the `subagent` tool** (pi's official example extension, see `AGENTS.md`, Setup)
  with `{agent: "mismagent-<name>", task: <the inputs the table names>}` and `agentScope: "both"`,
  so the definitions in `.pi/agents/` are visible. Each spawn is a fresh, isolated context: the
  fresh-context guarantee the reviewer relies on. Wait for its last message (the agent's
  `RESULT`/`VERDICT`) before reporting.
- **No always-on mode here:** type `/mismagent-build` again for the next action.
- **No hooks here:** on Claude Code two hooks stop an agent from merging, tagging or moving state
  and from editing the human's files. On pi the prompts say it and `mm check` verifies it.
"""


def convert_build():
    fm, body = parse_frontmatter(read(os.path.join(KERNEL, "commands", "build.md")))
    body = without_loop(body, "commands/build.md").rstrip() + "\n" + BUILD_NOTES
    emit_skill(OUT, adapt, GENERATED_NOTE, "build", fm.get("description", ""), body)
    ship_mm(OUT, adapt)
    front = "---\ndescription: %s\n" % json.dumps(adapt(fm.get("description", "")))
    if "argument-hint" in fm:
        front += "argument-hint: %s\n" % json.dumps(fm["argument-hint"])
    write(OUT, "prompts/mismagent-build.md", front + "---\n\n" + GENERATED_NOTE + "\n"
          "Read `" + SKILLS + "/mismagent-build/SKILL.md` and follow it exactly, for one action.\n"
          "The argument it was invoked with: `$ARGUMENTS`\n")


# Claude tool names -> pi tool names. WebSearch/WebFetch have no pi tool: bash (curl) stands in.
# Skill drops: pi subagents read a skill straight from .agents/skills/<name>/SKILL.md.
TOOL_MAP = {"Skill": [], "Bash": ["bash"], "Read": ["read"], "Edit": ["edit"], "Write": ["write"],
            "Glob": ["find", "ls"], "Grep": ["grep"], "WebSearch": ["bash"], "WebFetch": ["bash"]}

AGENT_NOTES = {
    "web": "> pi note (generated): WebSearch/WebFetch have no pi tool; `bash` (curl) stands in.\n",
    "skill": ("> pi note (generated): to load a skill, read `.agents/skills/<name>/SKILL.md` (the\n"
              "> plugin's skills carry the `mismagent-` prefix).\n"),
}


def convert_agents():
    for name in plugin_agents():
        fm, body = parse_frontmatter(read(os.path.join(KERNEL, "agents", name + ".md")))
        claude_tools = [t.strip() for t in fm.get("tools", "").split(",") if t.strip()]
        unknown = [t for t in claude_tools if t not in TOOL_MAP]
        if unknown:
            sys.exit("no pi mapping for tools %s: refusing to guess — update TOOL_MAP" % unknown)
        tools = []
        for t in claude_tools:
            tools += [p for p in TOOL_MAP[t] if p not in tools]
        notes = GENERATED_NOTE
        notes += AGENT_NOTES["web"] if {"WebSearch", "WebFetch"} & set(claude_tools) else ""
        notes += AGENT_NOTES["skill"] if "Skill" in claude_tools else ""
        front = "---\nname: %s\ndescription: %s\ntools: %s\n---\n" % (
            name, json.dumps(adapt(fm.get("description", ""))), ", ".join(tools))
        write(OUT, "agents/%s.md" % name, front + "\n" + notes + "\n" + adapt(body))


LEGEND = """
> **pi mapping (this packaging).** `/mismagent-build` is a **prompt template**; the other commands
> are pi **skills**: `/skill:mismagent-explore`, `/skill:mismagent-specify`,
> `/skill:mismagent-conventions`. The agents are definitions in `.pi/agents/` for the `subagent`
> tool, which `/mismagent-build` and the explore skill call with `agentScope: "both"`. The
> project's own conventions skill lives in `.agents/skills/conventions/`, and the project's
> settings (`## mismagent`: test, lint, smoke, thresholds) in this `AGENTS.md`. The Claude Code
> hooks are not shipped: the prompts and `mm check` hold their rules. pi has no per-agent reasoning
> knob: to make the challenger, the reviewer and the architect think harder, pin a stronger
> `model:` in their `.pi/agents/*.md`.

**Setup (once).** From the mismagent repo: `pi/install.sh <your-project-root>`. It copies the
skills into `<project>/.agents/skills/`, the prompt template into `<project>/.pi/prompts/`, the
agent definitions into `<project>/.pi/agents/`, and this file as the project's `AGENTS.md` (or
`AGENTS.mismagent.md` if one already exists: merge it), and anchors every tool path to the
absolute installed skills directory (re-run it after moving the project). The agents need pi's
official `subagent` example extension (pi repo,
`packages/coding-agent/examples/extensions/subagent/`: symlink `index.ts` and `agents.ts` into
`~/.pi/agent/extensions/subagent/`). Requires Python 3 (standard library only) for `mm`. Verify:
`/mismagent-build` autocompletes. Alternative global install (skills and prompts only):
`pi/install.sh --package <dir>`, then `pi install <dir>`.
"""


def write_agents_md():
    write(OUT, "AGENTS.md", "# mismAgent — pi packaging\n\n" + GENERATED_NOTE + LEGEND + "\n"
          + agents_md_body(adapt))


def write_manifest():
    manifest = {
        "name": "mismagent-pi",
        "version": version(),
        "description": ("mismAgent — pi packaging (GENERATED from the Claude Code plugin by "
                        "tools/generate-pi.py; do not edit)"),
        "keywords": ["pi-package"],
        "pi": {"skills": ["./skills"], "prompts": ["./prompts"]},
    }
    write(OUT, "package.json", json.dumps(manifest, indent=2) + "\n")


INSTALL_SH = r"""#!/bin/sh
# GENERATED by tools/generate-pi.py — installs the mismAgent pi packaging.
#   install.sh <project-root>     skills, prompts, agents and AGENTS.md into the project
#   install.sh --package <dir>    an anchored pi package (skills + prompts) for `pi install <dir>`
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
usage() { echo "usage: install.sh <project-root> | install.sh --package <dir>" >&2; exit 2; }
check_path() {  # the path is written quoted into commands: refuse what would break the quoting
  case "$1" in *'"'*|*'`'*|*'$'*|*'\'*) echo "install.sh: the path must not contain a quote, backtick, dollar or backslash" >&2; exit 2 ;; esac
}
anchor() {  # every path into the skills -> this installation's absolute skills directory
  ESC=$(printf '%s' "$1" | sed 's/[|&\\]/\\&/g')
  shift
  for f in "$@"; do
    [ -f "$f" ] || continue
    sed "s|@@MISMAGENT_SKILLS@@|$ESC|g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  done
}
case "${1:-}" in
  "") usage ;;
  --package)
    [ -n "${2:-}" ] && [ -z "${3:-}" ] || usage
    mkdir -p "$2"
    PKG=$(cd "$2" && pwd)
    check_path "$PKG"
    rm -rf "$PKG/skills" "$PKG/prompts"
    cp -R "$HERE/skills" "$HERE/prompts" "$HERE/package.json" "$PKG/"
    anchor "$PKG/skills" "$PKG"/skills/mismagent-*/SKILL.md "$PKG"/skills/mismagent-*/references/*.md \
      "$PKG"/skills/mismagent-*/scripts/*.py "$PKG"/prompts/mismagent-*.md
    chmod +x "$PKG/skills/mismagent-build/scripts/mm.py"
    echo "mismAgent pi package written to $PKG — install it with: pi install \"$PKG\""
    exit 0 ;;
esac
[ -z "${2:-}" ] || usage
mkdir -p "$1"
TARGET=$(cd "$1" && pwd)
check_path "$TARGET"
SKILLS="$TARGET/.agents/skills"

mkdir -p "$SKILLS" "$TARGET/.pi/prompts" "$TARGET/.pi/agents"
# the mismagent- names are this packaging's: replace them whole, so a retired piece goes too
rm -rf "$SKILLS"/mismagent-* "$TARGET"/.pi/prompts/mismagent-*.md "$TARGET"/.pi/agents/mismagent-*.md
cp -R "$HERE"/skills/mismagent-* "$SKILLS/"
cp "$HERE"/prompts/*.md "$TARGET/.pi/prompts/"
cp "$HERE"/agents/*.md "$TARGET/.pi/agents/"

if [ -f "$TARGET/AGENTS.md" ]; then
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.mismagent.md"
  echo "AGENTS.md already exists -> wrote AGENTS.mismagent.md (merge it into yours)."
else
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.md"
fi
anchor "$SKILLS" "$SKILLS"/mismagent-*/SKILL.md "$SKILLS"/mismagent-*/references/*.md \
  "$SKILLS"/mismagent-*/scripts/*.py "$TARGET"/.pi/prompts/mismagent-*.md \
  "$TARGET"/.pi/agents/mismagent-*.md "$TARGET/AGENTS.md" "$TARGET/AGENTS.mismagent.md"
chmod +x "$SKILLS/mismagent-build/scripts/mm.py"
echo "mismAgent (pi) installed into $TARGET — verify that /mismagent-build autocompletes."
echo "The agents need pi's subagent example extension (AGENTS.md, Setup), called with agentScope 'both'."
"""


def main():
    global OUT
    OUT = fresh(OUT, sys.argv, "generate-pi.py")
    print("generating pi/ from plugins/ ...")
    ship_skills(OUT, adapt, GENERATED_NOTE)
    convert_build()
    convert_agents()
    write_agents_md()
    write_manifest()
    write(OUT, "install.sh", INSTALL_SH, 0o755)
    check_tree(OUT, r"/skill:mismagent-([a-z0-9-]+)")
    print("done.")


if __name__ == "__main__":
    main()
