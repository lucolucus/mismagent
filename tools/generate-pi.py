#!/usr/bin/env python3
"""
generate-pi.py — derive the pi (pi.dev) packaging of mismAgent from the Claude Code plugin.

The Claude plugin (plugins/mismagent) is the ONLY source of
truth; pi/ is a GENERATED view (the methodology's derived-view rule: a derived view regenerated from a source,
never hand-maintained). Do not edit pi/ by hand — edit the plugin, then re-run this script.

Mapping (verified against pi.dev/docs/latest + the earendil-works/pi subagent example, 2026-07):
  plugin skill  SKILL.md (+ references/) -> pi/skills/mismagent-<name>/        (.agents/skills)
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
OUT = os.path.join(ROOT, "pi")

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


COMPOSER_DIR = ".agents/skills/mismagent-worker-composer"


# ---- text adaptation (deterministic, reviewable rules) -----------------------
def adapt(text, keep_args=False):
    """Claude-Code idioms -> pi idioms."""
    text = text.replace("`/mismagent:<name>`", "`/mismagent-<name>`")  # the wrappers' prompt templates
    # /mismagent:X — prompt template if X is a thin [agent] wrapper, skill otherwise
    text = re.sub(r"/mismagent:([a-z0-9-]+)",
                  lambda m: ("/mismagent-%s" if m.group(1) in WRAPPERS
                             else "/skill:mismagent-%s") % m.group(1), text)
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/board.py"',
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/board.py",
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/mismagent.py"', COMPOSER_DIR + "/scripts/mismagent.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/mismagent.py", COMPOSER_DIR + "/scripts/mismagent.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/CLI.md", COMPOSER_DIR + "/references/CLI.md")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/LOOP.md", COMPOSER_DIR + "/references/LOOP.md")
    text = text.replace("(Agent tool)", "(the `subagent` tool)")
    text = text.replace("(Agent tool,", "(the `subagent` tool,")
    if not keep_args:  # pi substitutes $ARGUMENTS in prompt templates, not in skills
        text = text.replace("$ARGUMENTS", "<the argument this skill was invoked with>")
    # the profile templates ship inside the explore skill's references/
    text = text.replace("`PROFILE.md`", "`.agents/skills/mismagent-explore/references/PROFILE.md`")
    text = text.replace("`profiles/example.md`",
                        "`.agents/skills/mismagent-explore/references/profile-example.md`")
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
            if val.startswith("'") and val.endswith("'") and len(val) > 1:
                val = val[1:-1].replace("''", "'")
            elif val.startswith('"') and val.endswith('"') and len(val) > 1:
                val = json.loads(val)
            fm[m.group(1)] = val
    return fm, text[end + 4:].lstrip("\n")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("  wrote %s" % os.path.relpath(path, ROOT))


# ---- skills ------------------------------------------------------------------
def emit_skill(name, description, body):
    front = "---\nname: mismagent-%s\ndescription: %s\n---\n" % (
        name, json.dumps(adapt(description)))
    content = front + "\n" + GENERATED_NOTE + "\n" + adapt(body)
    write(os.path.join(OUT, "skills", "mismagent-%s" % name, "SKILL.md"), content)


def convert_skills(plugin_dir):
    skills_dir = os.path.join(plugin_dir, "skills")
    if not os.path.isdir(skills_dir):
        return
    for name in sorted(os.listdir(skills_dir)):
        src = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(src):
            continue
        with open(src, encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        emit_skill(name, fm.get("description", ""), body)
        copy_references(os.path.join(skills_dir, name), "mismagent-%s" % name)


def copy_references(src_skill_dir, out_name):
    """A skill's references/ ship beside its SKILL.md (Markdown adapted, anything else copied)."""
    src = os.path.join(src_skill_dir, "references")
    if not os.path.isdir(src):
        return
    for fn in sorted(os.listdir(src)):
        path = os.path.join(src, fn)
        if not os.path.isfile(path):
            continue
        dest = os.path.join(OUT, "skills", out_name, "references", fn)
        if fn.endswith(".md"):
            with open(path, encoding="utf-8") as f:
                write(dest, adapt(f.read()))
        else:
            shutil.copy(path, _ensured(dest))
            print("  wrote %s" % os.path.relpath(dest, ROOT))


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

# generated packaging glue: pi's subagent tool spawns only NAMED agents, so the composer's review
# semantic review (a skill on Claude/Codex) needs a fresh-context host agent on pi.
REVIEWER_DESCRIPTION = (
    "GENERATED packaging glue (pi only) — fresh-context host for the mismagent-code-review "
    "skill. Spawned by the worker-composer at review (step 5) after mismagent-verifier; loads the skill and "
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
  AGENTS.md, Setup), with the mismAgent agent definitions in `.pi/agents/`; always pass
  `agentScope: "both"` so the project-local agents are visible. Every spawn is a fresh, isolated
  context — exactly the fresh-context guarantee the review relies on.
- **Parallel consumers in a wave — use the tool's parallel mode**: one
  `{agent: "mismagent-worker", task: ...}` entry per ready block, each task carrying `block_id`,
  `block_type`, `context`, the block-type skill names (e.g.
  `mismagent-realize-aggregate` — the worker reads them from `.agents/skills/<name>/SKILL.md`),
  the path of the block's rich `<id>.md` spec and the side's gate commands. The extension caps a
  call at 8 tasks (4 concurrent) — size waves accordingly. Ask each worker to end with the RESULT
  handoff (`status: READY-FOR-REVIEW|BOUNCED|BLOCKED`, file list, notes) and route it to step 4
  as usual.
- **Review (step 5)**: spawn `{agent: "mismagent-verifier", task: <block + gate>}`
  (structural), then `{agent: "mismagent-reviewer", task: <block id + diff scope>}` — a generated
  glue agent whose only job is to load `.agents/skills/mismagent-code-review/SKILL.md` in fresh
  context and apply it to the block's diff (read-only). A `chain: [...]` with `{previous}` can
  wire worker → verifier → reviewer per block when sequential handoffs are preferable.
- **Model routing on pi:** bind the tiers to your pi models in the profile's
  `build.model_routing.tiers`. Pass the routed model on each task when your `subagent` tool accepts
  a per-task model; when it does not, the `model:` of the agent definition in `.pi/agents/`
  applies — write `model=default` in the ledger line, never a tier binding you could not apply.
  Size `build.max_parallel_workers` to the tool's cap (8 tasks per call, 4 concurrent).
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
    # the build's deterministic tool + its interface, beside the skill that calls it
    for src, sub in (("mismagent.py", "scripts"), ("board.py", "scripts"), ("CLI.md", "references"),
                     ("LOOP.md", "references")):
        path = os.path.join(KERNEL, "tools", src)
        if not os.path.exists(path):
            print("  WARNING: %s missing — not shipped" % path)
            continue
        dest = _ensured(os.path.join(OUT, "skills", "mismagent-worker-composer", sub, src))
        if src.endswith(".md"):  # the interface doc names the plugin path: rewrite it
            with open(path, encoding="utf-8") as f, open(dest, "w", encoding="utf-8") as g:
                g.write(adapt(f.read()))
        else:
            shutil.copy(path, dest)
        print("  wrote pi/skills/mismagent-worker-composer/%s/%s" % (sub, src))


def _ensured(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# ---- thin agent-wrapper commands -> prompt templates -------------------------
PROMPT_NOTE = ("> `[agent]` dispatch: needs pi's `subagent` example extension (AGENTS.md, Setup);\n"
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
    "**Setup (once).** From the mismagent repo: `pi/install.sh <your-project-root>` "
    "It copies the skills "
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
    "context — the guarantee the review relies on). The board script lives at "
    "`.agents/skills/mismagent-board/scripts/board.py`. The worker-composer's parallel waves map "
    "onto the subagent tool's parallel mode (max 8 tasks per call, 4 concurrent — see its "
    "skill's pi execution notes); `mismagent-reviewer` is generated glue hosting the "
    "`mismagent-code-review` skill in fresh context. pi has no per-agent reasoning knob — to "
    "think harder on the adversarial roles (challenger/verifier/architect), pin a stronger "
    "`model:` in their `.pi/agents/*.md`.\n"
)

def convert_methodology():
    """The methodology ships WHOLE (no paragraph surgery): its H1 is replaced by the pi header,
    setup and legend; the rest is adapted like any other file."""
    path = os.path.join(KERNEL, "methodology", "mismagent.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("# "):
        sys.exit("%s must start with its '# ' title line — generate-pi.py replaces it" % path)
    body = adapt(text.split("\n", 1)[1] if "\n" in text else "")
    header = ("# mismAgent — pi packaging\n\n" + GENERATED_NOTE + PI_LEGEND + "\n" + PI_SETUP + "\n")
    write(os.path.join(OUT, "AGENTS.md"), header + body)


# ---- the generated tree must be self-contained ---------------------------------
CLAUDE_ONLY = ("$CLAUDE_PLUGIN_ROOT", "redesign/composer-spec", "/plugin marketplace", "/mismagent:",
               "/mismagent-cross-deploy:")


def check_tree():
    """Fail loudly on a Claude-only idiom left in the output, a relative Markdown link, a
    `.agents/skills/...` path or a skill's `references/<file>` that does not resolve in pi/."""
    bad = []
    for d, _, fns in os.walk(OUT):
        for fn in fns:
            if not fn.endswith((".md", ".toml")):
                continue
            path = os.path.join(d, fn)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(path, ROOT)
            bad += ["%s: Claude-only idiom %r" % (rel, t) for t in CLAUDE_ONLY if t in text]
            bad += ["%s: /skill:mismagent-%s is no shipped skill" % (rel, n)
                    for n in re.findall(r"/skill:mismagent-([a-z0-9-]+)", text)
                    if not os.path.isdir(os.path.join(OUT, "skills", "mismagent-" + n))]
            for link in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
                if not re.match(r"^[a-z]+:", link) and not os.path.exists(os.path.join(d, link)):
                    bad.append("%s: link %s does not resolve" % (rel, link))
            for p in re.findall(r"\.agents/skills/([A-Za-z0-9_./-]+)", text):
                p = p.rstrip(".")
                if "<" not in p and not os.path.exists(os.path.join(OUT, "skills", p)):
                    bad.append("%s: path .agents/skills/%s not shipped" % (rel, p))
            skill = re.match(r"skills/([^/]+)/", os.path.relpath(path, OUT))
            for p in re.findall(r"`references/([A-Za-z0-9_.-]+)`", text) if skill else []:
                if not os.path.exists(os.path.join(OUT, "skills", skill.group(1), "references", p)):
                    bad.append("%s: references/%s not shipped" % (rel, p))
    if bad:
        sys.exit("generated pi/ is not self-contained:\n  " + "\n  ".join(bad))


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
TARGET=${1:?usage: install.sh <project-root>}
case "${2:-}" in
  "") ;;
  --with-cross-deploy)
    echo "install.sh: --with-cross-deploy was removed in v0.18.0 (cross-deploy is no longer a module;" \
      "keep such contracts as project files). Run: install.sh <project-root>" >&2
    exit 2 ;;
  *) echo "usage: install.sh <project-root>" >&2; exit 2 ;;
esac

mkdir -p "$TARGET/.agents/skills" "$TARGET/.pi/prompts" "$TARGET/.pi/agents"
# skills retired in v0.18.0: remove them from an upgraded installation
for old in create-contract seam-cross-deploy seam-in-process; do
  rm -rf "$TARGET/.agents/skills/mismagent-$old"
done
for d in "$HERE"/skills/*/; do
  name=$(basename "$d")
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
echo "[agent] steps need pi's subagent example extension (AGENTS.md, Setup) with agentScope 'both'."
"""


def main():
    global WRAPPERS
    WRAPPERS = wrapper_commands()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    print("generating pi/ from plugins/ ...")
    convert_skills(KERNEL)
    convert_agents()
    convert_commands()
    convert_prompts()
    copy_profile_templates()
    convert_methodology()
    write_manifest()
    write(os.path.join(OUT, "install.sh"), INSTALL_SH)
    os.chmod(os.path.join(OUT, "install.sh"), 0o755)
    check_tree()
    print("done.")


if __name__ == "__main__":
    main()
