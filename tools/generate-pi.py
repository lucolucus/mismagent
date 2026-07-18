#!/usr/bin/env python3
"""
generate-pi.py — derive the pi (pi.dev) packaging of mismAgent from the Claude Code plugin.

The Claude plugin (plugins/mismagent + plugins/mismagent-cross-deploy) is the ONLY source of
truth; pi/ is a GENERATED view (methodology rule #3: a derived view regenerated from a source,
never hand-maintained). Do not edit pi/ by hand — edit the plugin, then re-run this script.

Mapping (verified against pi.dev/docs/latest + the earendil-works/pi subagent example, 2026-07):
  plugin skill  SKILL.md            -> pi/skills/mismagent-<name>/SKILL.md    (.agents/skills)
  command       worker-composer.md  -> skill mismagent-worker-composer        (model-referenceable)
  command       board.md + board.py -> skill mismagent-board (script in scripts/)
  command       model.md            -> skill mismagent-model
  thin agent-wrapper commands       -> pi/prompts/mismagent-<n>.md  (prompt templates, /mismagent-<n>;
                                       pi substitutes $ARGUMENTS natively — unlike Codex, kept)
  plugin agent  agents/<n>.md       -> pi/agents/<n>.md   (subagent-extension format: name/
                                       description/tools md+frontmatter, discovered in .pi/agents/)
  + mismagent-reviewer              -> generated glue agent: fresh-context host for code-review
  methodology   mismagent.md        -> pi/AGENTS.md  (pi reads AGENTS.md from the project cwd)
  package.json                      -> pi package manifest (skills+prompts, `pi install` alternative)

Usage: python3 tools/generate-pi.py   (from the repo root)
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL = os.path.join(ROOT, "plugins", "mismagent")
CROSS = os.path.join(ROOT, "plugins", "mismagent-cross-deploy")
OUT = os.path.join(ROOT, "pi")

CROSS_DEPLOY_SKILLS = {"create-contract", "seam-cross-deploy"}
# commands that stay skills (referenced BY other skills/agents mid-flow, and board carries a script)
SKILL_COMMANDS = ("worker-composer", "board", "model")

GENERATED_NOTE = (
    "> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-pi.py`; the\n"
    "> Claude Code plugin is the source of truth. Edit the source, then regenerate.\n"
)


def wrapper_commands():
    """Commands that become prompt templates (thin [agent] dispatchers)."""
    cmds = {fn[:-3] for fn in os.listdir(os.path.join(KERNEL, "commands")) if fn.endswith(".md")}
    return cmds - set(SKILL_COMMANDS)


WRAPPERS = None  # filled in main() — needed by adapt()


# ---- text adaptation (deterministic, reviewable rules) -----------------------
def adapt(text, keep_args=False):
    """Claude-Code idioms -> pi idioms."""
    # module-namespaced skill first (more specific than the generic rule)
    text = text.replace("/mismagent-cross-deploy:create-contract",
                        "/skill:mismagent-create-contract")
    # /mismagent:X — prompt template if X is a thin [agent] wrapper, skill otherwise
    text = re.sub(r"/mismagent:([a-z0-9-]+)",
                  lambda m: ("/mismagent-%s" if m.group(1) in WRAPPERS
                             else "/skill:mismagent-%s") % m.group(1), text)
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/board.py"',
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/board.py",
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("(Agent tool)", "(the `subagent` tool)")
    text = text.replace("(Agent tool,", "(the `subagent` tool,")
    if not keep_args:  # pi substitutes $ARGUMENTS in prompt templates, not in skills
        text = text.replace("$ARGUMENTS", "<the argument this skill was invoked with>")
    # the profile templates ship inside the explore skill's references/
    text = text.replace("`PROFILE.md`", "`.agents/skills/mismagent-explore/references/PROFILE.md`")
    text = text.replace("`profiles/example.md`",
                        "`.agents/skills/mismagent-explore/references/profile-example.md`")
    text = text.replace("enable it in the marketplace",
                        "install it with `install.sh --with-cross-deploy`")
    return text


def parse_frontmatter(text):
    """Return (dict, body). Minimal: single-line `key: value` fields only."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            val = m.group(2).strip()
            if (val.startswith("'") and val.endswith("'")) or \
               (val.startswith('"') and val.endswith('"')):
                val = val[1:-1]
            fm[m.group(1)] = val
    return fm, text[end + 4:].lstrip("\n")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("  wrote %s" % os.path.relpath(path, ROOT))


# ---- skills ------------------------------------------------------------------
def emit_skill(name, description, body, extra_note=""):
    front = "---\nname: mismagent-%s\ndescription: %s\n---\n" % (
        name, json.dumps(adapt(description)))
    content = front + "\n" + GENERATED_NOTE + extra_note + "\n" + adapt(body)
    write(os.path.join(OUT, "skills", "mismagent-%s" % name, "SKILL.md"), content)


def convert_skills(plugin_dir, cross=False):
    skills_dir = os.path.join(plugin_dir, "skills")
    if not os.path.isdir(skills_dir):
        return
    for name in sorted(os.listdir(skills_dir)):
        src = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(src):
            continue
        with open(src, encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        note = ""
        if cross or name in CROSS_DEPLOY_SKILLS:
            note = ("> Cross-deploy module: install only when a boundary crosses a deploy unit\n"
                    "> (`install.sh --with-cross-deploy`).\n")
        emit_skill(name, fm.get("description", ""), body, note)


# ---- agents -> subagent-extension markdown -----------------------------------
# Claude tool names -> pi tool names (subagent-extension `tools:` list). WebSearch/WebFetch have
# no pi tool: bash (curl) substitutes, noted in the generated body. Skill drops: pi subagents read
# the skills straight from .agents/skills/<name>/SKILL.md.
TOOL_MAP = {
    "Skill": [], "Bash": ["bash"], "Read": ["read"], "Edit": ["edit"], "Write": ["write"],
    "Glob": ["find", "ls"], "Grep": ["grep"], "WebSearch": ["bash"], "WebFetch": ["bash"],
}

WEB_NOTE = ("> pi note (generated): WebSearch/WebFetch have no pi equivalent — `bash` (curl)\n"
            "> substitutes for web access here.\n")

# generated packaging glue: pi's subagent tool spawns only NAMED agents, so the composer's D1
# semantic review (a skill on Claude/Codex) needs a fresh-context host agent on pi.
REVIEWER_DESCRIPTION = (
    "GENERATED packaging glue (pi only) — fresh-context host for the mismagent-code-review "
    "skill. Spawned by the worker-composer at D1 after mismagent-verifier; loads the skill and "
    "applies it to the diff of ONE block. Read-only — finds and triages (HIGH|MED|LOW -> "
    "Decision|Patch|Defer), does not fix.")

REVIEWER_AGENT = """---
name: mismagent-reviewer
description: %s
tools: read, grep, find, ls, bash
---

%sYou are a fresh-context reviewer: you did not see the development, so you don't trust — you hunt.
Read `.agents/skills/mismagent-code-review/SKILL.md` and execute it **exactly** on the block's
diff named in your task (block id, context, diff scope). Use bash only to inspect (`git diff` /
`git log` / `git show`, the gate commands read-only) — never to write. Return the skill's finding
triage as your final message.
""" % (json.dumps(REVIEWER_DESCRIPTION), GENERATED_NOTE)


def map_tools(tools_field):
    mapped, noted_web = [], False
    for t in [t.strip() for t in tools_field.split(",") if t.strip()]:
        if t not in TOOL_MAP:
            sys.exit("no pi mapping for tool %r: refusing to guess — update TOOL_MAP" % t)
        if t in ("WebSearch", "WebFetch"):
            noted_web = True
        for p in TOOL_MAP[t]:
            if p not in mapped:
                mapped.append(p)
    return mapped, noted_web


def convert_agents():
    for fn in sorted(os.listdir(os.path.join(KERNEL, "agents"))):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(KERNEL, "agents", fn), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        tools, noted_web = map_tools(fm.get("tools", ""))
        front = "---\nname: %s\ndescription: %s\ntools: %s\n---\n" % (
            fm["name"], json.dumps(adapt(fm.get("description", ""))), ", ".join(tools))
        # `model: inherit` -> omitted (pi inherits the session model when unset)
        note = GENERATED_NOTE + (WEB_NOTE if noted_web else "")
        write(os.path.join(OUT, "agents", "%s.md" % fm["name"]),
              front + "\n" + note + "\n" + adapt(body))
    write(os.path.join(OUT, "agents", "mismagent-reviewer.md"), REVIEWER_AGENT)


# ---- commands that survive as skills ----------------------------------------
COMPOSER_PI_NOTES = """
## pi execution notes (generated — how to run the waves on this harness)
- **All subagent dispatch goes through the `subagent` tool** (pi's official example extension —
  AGENTS.md §0), with the mismAgent agent definitions in `.pi/agents/`; always pass
  `agentScope: "both"` so the project-local agents are visible. Every spawn is a fresh, isolated
  context — exactly the fresh-context guarantee D1 relies on.
- **Parallel consumers in a wave — use the tool's parallel mode**: one
  `{agent: "mismagent-worker", task: ...}` entry per ready block, each task carrying `block_id`,
  `block_type`, `context`, the `select(block-type × projection)` skill names (e.g.
  `mismagent-realize-aggregate` — the worker reads them from `.agents/skills/<name>/SKILL.md`),
  the path of the block's rich `<id>.md` spec and the side's gate commands. The extension caps a
  call at 8 tasks (4 concurrent) — size waves accordingly. Ask each worker to end with the RESULT
  handoff (`status: READY-FOR-REVIEW|BOUNCED|BLOCKED`, file list, notes) and route it to §3 D1
  as usual.
- **D1 after the worker**: spawn `{agent: "mismagent-verifier", task: <block + gate>}`
  (structural), then `{agent: "mismagent-reviewer", task: <block id + diff scope>}` — a generated
  glue agent whose only job is to load `.agents/skills/mismagent-code-review/SKILL.md` in fresh
  context and apply it to the block's diff (read-only). A `chain: [...]` with `{previous}` can
  wire worker → verifier → reviewer per block when sequential handoffs are preferable.
"""


def convert_commands():
    for cmd in SKILL_COMMANDS:
        with open(os.path.join(KERNEL, "commands", "%s.md" % cmd), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        if cmd == "worker-composer":
            body = body.rstrip() + "\n" + COMPOSER_PI_NOTES
        emit_skill(cmd, fm.get("description", ""), body)
    shutil.copy(os.path.join(KERNEL, "tools", "board.py"),
                _ensured(os.path.join(OUT, "skills", "mismagent-board", "scripts", "board.py")))
    print("  wrote pi/skills/mismagent-board/scripts/board.py")


def _ensured(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# ---- thin agent-wrapper commands -> prompt templates -------------------------
PROMPT_NOTE = ("> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md §0);\n"
               "> call it with `agentScope: \"both\"` so the `.pi/agents/` definitions are "
               "visible.\n")


def convert_prompts():
    for cmd in sorted(WRAPPERS):
        with open(os.path.join(KERNEL, "commands", "%s.md" % cmd), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        front = "---\ndescription: %s\n" % json.dumps(adapt(fm.get("description", "")))
        if "argument-hint" in fm:
            front += "argument-hint: %s\n" % json.dumps(fm["argument-hint"])
        front += "---\n"
        write(os.path.join(OUT, "prompts", "mismagent-%s.md" % cmd),
              front + "\n" + GENERATED_NOTE + PROMPT_NOTE + "\n" + adapt(body, keep_args=True))


# ---- profile templates (inside the explore skill's references/) --------------
def copy_profile_templates():
    ref = os.path.join(OUT, "skills", "mismagent-explore", "references")
    for src, dst in ((os.path.join(KERNEL, "PROFILE.md"), "PROFILE.md"),
                     (os.path.join(KERNEL, "profiles", "example.md"), "profile-example.md")):
        with open(src, encoding="utf-8") as f:
            write(os.path.join(ref, dst), adapt(f.read()))


# ---- AGENTS.md from the methodology ------------------------------------------
PI_SETUP = (
    "**0 · Setup (once).** From the mismagent repo: `pi/install.sh <your-project-root>` "
    "(add `--with-cross-deploy` only if boundaries cross deploy units). It copies the skills "
    "into `<project>/.agents/skills/`, the prompt templates into `<project>/.pi/prompts/`, the "
    "subagent definitions into `<project>/.pi/agents/`, and this file as the project's "
    "`AGENTS.md` (or `AGENTS.mismagent.md` if one already exists — merge it). `[agent]` steps "
    "additionally need pi's official `subagent` example extension (pi repo, "
    "`packages/coding-agent/examples/extensions/subagent/` — symlink `index.ts` + `agents.ts` "
    "into `~/.pi/agent/extensions/subagent/`), always called with `agentScope: \"both\"`. "
    "Verify: `/skill:mismagent-explore` autocompletes. Alternative global install "
    "(skills+prompts only): `pi install <path-to-mismagent-repo>/pi`."
)

PI_LEGEND = (
    "\n> **pi mapping (this packaging).** `[skill]`/`[command]` steps are pi **skills** — invoke "
    "with `/skill:mismagent-<name>` (pi also loads them on demand; names carry the `mismagent-` "
    "prefix because pi's skill space is flat). `[agent]` steps are **prompt templates** "
    "(`/mismagent-<name>`) that dispatch the matching subagent definition in `.pi/agents/` "
    "through the `subagent` tool (`agentScope: \"both\"`; every spawn is a fresh isolated "
    "context — the guarantee D1 relies on). The board script lives at "
    "`.agents/skills/mismagent-board/scripts/board.py`. The worker-composer's parallel waves map "
    "onto the subagent tool's parallel mode (max 8 tasks per call, 4 concurrent — see its "
    "skill's pi execution notes); `mismagent-reviewer` is generated glue hosting the "
    "`mismagent-code-review` skill in fresh context. pi has no per-agent reasoning knob — to "
    "think harder on the adversarial roles (challenger/verifier/architect), pin a stronger "
    "`model:` in their `.pi/agents/*.md`.\n"
)

METHODOLOGY_REWRITES = (
    # repo-internal pointers make no sense inside a consuming project
    (r"> Extended reasoning: `redesign/composer-spec\.md`.*?outside the registry\)\.",
     "> Extended reasoning lives in the mismagent source repo\n"
     "> (`plugins/mismagent/redesign/composer-spec.md`)."),
    # the "how to invoke" paragraph and the run-sheet legend speak slash-command; re-speak pi
    (r"\*How to invoke it \(in order\)\..*?headless form\.\):\*",
     "*How to invoke it (in order). `[skill]`/`[command]` are pi **skills** — invoke with "
     "`/skill:mismagent-<name>`; `[agent]` is a **prompt template** — type `/mismagent-<name>` "
     "and it dispatches the subagent of the same name via the `subagent` tool. You can still ask "
     "pi to *\"spawn `mismagent-X` via the subagent tool\"* if you prefer the headless form.):*"),
    (r"Legend: \*\*you type\*\* the slash-commands.*?dispatch `mismagent-X`\"\*\.",
     "Legend: `[skill]`/`[command]` are skills **you invoke** as `/skill:mismagent-<name>`; "
     "`[agent]` is a **prompt template you type** as `/mismagent-<name>` — it dispatches the "
     "subagent of the same name through the `subagent` tool (fallback: ask pi to *\"spawn "
     "`mismagent-X` via the subagent tool\"*)."),
)


def convert_methodology():
    with open(os.path.join(KERNEL, "methodology", "mismagent.md"), encoding="utf-8") as f:
        text = f.read()
    # swap the Claude-plugin setup paragraph for the pi install one
    text, n = re.subn(r"\*\*0 · Setup \(once\)\.\*\*.*?(?=\n\n)", PI_SETUP,
                      text, count=1, flags=re.S)
    if n != 1:
        sys.exit("methodology setup paragraph not found — update generate-pi.py")
    for pattern, repl in METHODOLOGY_REWRITES:
        text, n = re.subn(pattern, lambda _m, r=repl: r, text, count=1, flags=re.S)
        if n != 1:
            sys.exit("methodology passage for %r not found — update generate-pi.py" % pattern[:40])
    text = adapt(text)
    header = ("# mismAgent — pi packaging\n\n" + GENERATED_NOTE + PI_LEGEND + "\n")
    # drop the original H1 line, keep the rest
    body = text.split("\n", 1)[1]
    write(os.path.join(OUT, "AGENTS.md"), header + body)


# ---- package.json + install.sh -----------------------------------------------
def write_manifest():
    with open(os.path.join(KERNEL, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    manifest = {
        "name": "mismagent-pi",
        "version": version,
        "description": ("mismAgent method — pi packaging (GENERATED from the Claude Code plugin "
                        "by tools/generate-pi.py; do not edit)"),
        "keywords": ["pi-package"],
        "pi": {"skills": ["./skills"], "prompts": ["./prompts"]},
    }
    write(os.path.join(OUT, "package.json"), json.dumps(manifest, indent=2) + "\n")


INSTALL_SH = """#!/bin/sh
# GENERATED by tools/generate-pi.py — installs the mismAgent pi packaging into a project.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=${1:?usage: install.sh <project-root> [--with-cross-deploy]}
WITH_CROSS=false
[ "${2:-}" = "--with-cross-deploy" ] && WITH_CROSS=true

mkdir -p "$TARGET/.agents/skills" "$TARGET/.pi/prompts" "$TARGET/.pi/agents"
for d in "$HERE"/skills/*/; do
  name=$(basename "$d")
  case "$name" in
    mismagent-create-contract|mismagent-seam-cross-deploy)
      $WITH_CROSS || continue ;;
  esac
  rm -rf "$TARGET/.agents/skills/$name"
  cp -R "$d" "$TARGET/.agents/skills/$name"
done
cp "$HERE"/prompts/*.md "$TARGET/.pi/prompts/"
cp "$HERE"/agents/*.md "$TARGET/.pi/agents/"

if [ -f "$TARGET/AGENTS.md" ]; then
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.mismagent.md"
  echo "AGENTS.md already exists -> wrote AGENTS.mismagent.md (merge it into yours)."
else
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.md"
fi
echo "mismAgent (pi) installed into $TARGET — verify with /skill:mismagent-explore."
echo "[agent] steps need pi's subagent example extension (AGENTS.md, step 0) with agentScope 'both'."
"""


def main():
    global WRAPPERS
    WRAPPERS = wrapper_commands()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    print("generating pi/ from plugins/ ...")
    convert_skills(KERNEL)
    convert_skills(CROSS, cross=True)
    convert_agents()
    convert_commands()
    convert_prompts()
    copy_profile_templates()
    convert_methodology()
    write_manifest()
    write(os.path.join(OUT, "install.sh"), INSTALL_SH)
    os.chmod(os.path.join(OUT, "install.sh"), 0o755)
    print("done.")


if __name__ == "__main__":
    main()
