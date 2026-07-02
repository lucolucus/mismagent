#!/usr/bin/env python3
"""
generate-codex.py — derive the Codex/OpenAI packaging of mismAgent from the Claude Code plugin.

The Claude plugin (plugins/mismagent + plugins/mismagent-cross-deploy) is the ONLY source of
truth; codex/ is a GENERATED view (methodology rule #3: a derived view regenerated from a source,
never hand-maintained). Do not edit codex/ by hand — edit the plugin, then re-run this script.

Mapping (verified against developers.openai.com/codex, 2026-07):
  plugin skill  SKILL.md            -> codex/skills/mismagent-<name>/SKILL.md   (.agents/skills)
  plugin agent  agents/<n>.md       -> codex/agents/<n>.toml                    (.codex/agents)
  command       worker-composer.md  -> skill mismagent-worker-composer
  command       board.md + board.py -> skill mismagent-board (script in scripts/)
  methodology   mismagent.md        -> codex/AGENTS.md
  thin agent-wrapper commands       -> dropped (Codex spawns subagents on explicit ask)

Usage: python3 tools/generate-codex.py   (from the repo root)
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL = os.path.join(ROOT, "plugins", "mismagent")
CROSS = os.path.join(ROOT, "plugins", "mismagent-cross-deploy")
OUT = os.path.join(ROOT, "codex")

CROSS_DEPLOY_SKILLS = {"create-contract", "seam-cross-deploy"}

GENERATED_NOTE = (
    "> **GENERATED — do not edit.** Derived from `plugins/` by `tools/generate-codex.py`; the\n"
    "> Claude Code plugin is the source of truth. Edit the source, then regenerate.\n"
)


# ---- text adaptation (deterministic, reviewable rules) -----------------------
def adapt(text):
    """Claude-Code idioms -> Codex idioms."""
    # module-namespaced command first (more specific than the generic rule)
    text = text.replace("/mismagent-cross-deploy:create-contract", "$mismagent-create-contract")
    text = re.sub(r"/mismagent:([a-z0-9-]+)", r"$mismagent-\1", text)
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/board.py"',
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/board.py",
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("(Agent tool)", "(spawn it as a Codex subagent)")
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


# ---- agents -> TOML ----------------------------------------------------------
def toml_multiline(text):
    if "'''" in text:
        sys.exit("cannot TOML-encode (contains ''' literal): refusing to guess an escape")
    return "'''\n%s\n'''" % text


# adversarial / guarantor roles think harder; the rest inherit a medium effort
REASONING_EFFORT = {
    "mismagent-challenger": "high",   # must find the kill-shot, not a courtesy PROCEED
    "mismagent-verifier": "high",     # the deterministic gate before the merge
    "mismagent-architect": "high",    # foundational decisions + boundary guarantees
}


def convert_agents():
    for fn in sorted(os.listdir(os.path.join(KERNEL, "agents"))):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(KERNEL, "agents", fn), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        name = fm["name"]
        tools = fm.get("tools", "")
        writes = any(t in tools for t in ("Bash", "Write", "Edit"))
        sandbox = "workspace-write" if writes else "read-only"
        toml = (
            "# GENERATED from plugins/mismagent/agents/%s by tools/generate-codex.py — do not edit.\n"
            "name = %s\n"
            "description = %s\n"
            "sandbox_mode = %s\n"
            "model_reasoning_effort = %s\n"
            "developer_instructions = %s\n"
        ) % (fn, json.dumps(name), json.dumps(adapt(fm.get("description", ""))),
             json.dumps(sandbox), json.dumps(REASONING_EFFORT.get(name, "medium")),
             toml_multiline(adapt(body)))
        write(os.path.join(OUT, "agents", "%s.toml" % name), toml)


# ---- commands that survive as skills ----------------------------------------
COMPOSER_CODEX_NOTES = """
## Codex execution notes (generated — how to run the waves on this harness)
- **Workers and the verifier are Codex subagents** (`.codex/agents/`): spawn them explicitly; each
  spawn is a fresh, independent session — exactly the fresh-context guarantee D1 relies on.
  **`code-review` is a skill**: run it by spawning a plain subagent instructed to apply
  `mismagent-code-review` on the block's diff (same fresh-context effect, no TOML needed).
- **Parallel consumers in a wave — use `spawn_agents_on_csv`** (one worker per ready block):
  1. write a CSV with one row per ready block: `block_id,block_type,context,skills,spec_path`
     (`skills` = the `select(block-type × projection)` names, e.g. `mismagent-realize-aggregate`;
     `spec_path` = the block's rich `<id>.md` file);
  2. call `spawn_agents_on_csv` with `id_column: block_id`, `instruction` templated on those
     columns ("You are mismagent-worker. Realize block {block_id} ({block_type}, {context}): load
     the skills {skills}, follow the spec at {spec_path}, …"), an `output_schema` mirroring the
     worker's RESULT handoff (`status: READY-FOR-REVIEW|BOUNCED|BLOCKED`, `file_list`, `notes`),
     and `max_concurrency` = the wave's cap;
  3. each row's `result_json` is the worker handoff → route it to §3 D1 as usual.
- **Concurrency/config:** the global `[agents]` settings gate this (`max_threads` default 6,
  `max_depth` 1 — you run in the main thread, so depth is never exceeded).
"""


def convert_commands():
    for cmd, skill in (("worker-composer", "worker-composer"), ("board", "board")):
        with open(os.path.join(KERNEL, "commands", "%s.md" % cmd), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        if cmd == "worker-composer":
            body = body.rstrip() + "\n" + COMPOSER_CODEX_NOTES
        emit_skill(skill, fm.get("description", ""), body)
    shutil.copy(os.path.join(KERNEL, "tools", "board.py"),
                _ensured(os.path.join(OUT, "skills", "mismagent-board", "scripts", "board.py")))
    print("  wrote codex/skills/mismagent-board/scripts/board.py")


def _ensured(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# ---- profile templates (inside the explore skill's references/) --------------
def copy_profile_templates():
    ref = os.path.join(OUT, "skills", "mismagent-explore", "references")
    for src, dst in ((os.path.join(KERNEL, "PROFILE.md"), "PROFILE.md"),
                     (os.path.join(KERNEL, "profiles", "example.md"), "profile-example.md")):
        with open(src, encoding="utf-8") as f:
            write(os.path.join(ref, dst), adapt(f.read()))


# ---- AGENTS.md from the methodology ------------------------------------------
CODEX_SETUP = (
    "**0 · Setup (once).** From the mismagent repo: `codex/install.sh <your-project-root>` "
    "(add `--with-cross-deploy` only if boundaries cross deploy units). It copies the skills "
    "into `<project>/.agents/skills/`, the subagents into `<project>/.codex/agents/`, and this "
    "file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists — merge it). "
    "Verify: `/skills` lists `mismagent-explore`."
)

CODEX_LEGEND = (
    "\n> **Codex mapping (this packaging).** `[skill]`/`[command]` steps are Codex **skills** — "
    "invoke with `$mismagent-<name>` (or `/skills`). `[agent]` steps are Codex **subagents** in "
    "`.codex/agents/` — ask Codex to *\"spawn `mismagent-<name>` on <input>\"* (Codex spawns them "
    "only on explicit request, which matches the run-sheet). Skill names carry the `mismagent-` "
    "prefix because Codex has no namespaces. The board script lives at "
    "`.agents/skills/mismagent-board/scripts/board.py`. Subagents ship with a tuned "
    "`model_reasoning_effort` (challenger/verifier/architect: high) and a `sandbox_mode` matching "
    "their role (challenger: read-only). The worker-composer's parallel waves map onto "
    "`spawn_agents_on_csv` (see its skill's Codex execution notes); the `[agents]` config "
    "(`max_threads`, default 6) is the concurrency cap.\n"
)


METHODOLOGY_REWRITES = (
    # repo-internal pointers make no sense inside a consuming project
    (r"> Extended reasoning: `redesign/composer-spec\.md`.*?outside the registry\)\.",
     "> Extended reasoning lives in the mismagent source repo\n"
     "> (`plugins/mismagent/redesign/composer-spec.md`)."),
    # the "how to invoke" paragraph and the run-sheet legend speak slash-command; re-speak Codex
    (r"\*How to invoke it \(in order\)\..*?headless form\.\):\*",
     "*How to invoke it (in order). `[skill]`/`[command]` are Codex **skills** — invoke with "
     "`$mismagent-<name>`; `[agent]` is a Codex **subagent** — ask Codex to *\"spawn "
     "`mismagent-<name>` on <input>\"* (it spawns subagents only on explicit request).:*"),
    (r"Legend: \*\*you type\*\* the slash-commands.*?dispatch `mismagent-X`\"\*\.",
     "Legend: `[skill]`/`[command]` are skills **you invoke** as `$mismagent-<name>`; `[agent]` is "
     "a **subagent you ask Codex to spawn** (*\"spawn `mismagent-architect` on …\"*)."),
)


def convert_methodology():
    with open(os.path.join(KERNEL, "methodology", "mismagent.md"), encoding="utf-8") as f:
        text = f.read()
    # swap the Claude-plugin setup paragraph for the Codex install one
    text, n = re.subn(r"\*\*0 · Setup \(once\)\.\*\*.*?(?=\n\n)", CODEX_SETUP,
                      text, count=1, flags=re.S)
    if n != 1:
        sys.exit("methodology setup paragraph not found — update generate-codex.py")
    for pattern, repl in METHODOLOGY_REWRITES:
        text, n = re.subn(pattern, lambda _m, r=repl: r, text, count=1, flags=re.S)
        if n != 1:
            sys.exit("methodology passage for %r not found — update generate-codex.py" % pattern[:40])
    text = adapt(text)
    header = ("# mismAgent — Codex packaging\n\n" + GENERATED_NOTE + CODEX_LEGEND + "\n")
    # drop the original H1 line, keep the rest
    body = text.split("\n", 1)[1]
    write(os.path.join(OUT, "AGENTS.md"), header + body)


# ---- install.sh ---------------------------------------------------------------
INSTALL_SH = """#!/bin/sh
# GENERATED by tools/generate-codex.py — installs the mismAgent Codex packaging into a project.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=${1:?usage: install.sh <project-root> [--with-cross-deploy]}
WITH_CROSS=false
[ "${2:-}" = "--with-cross-deploy" ] && WITH_CROSS=true

mkdir -p "$TARGET/.agents/skills" "$TARGET/.codex/agents"
for d in "$HERE"/skills/*/; do
  name=$(basename "$d")
  case "$name" in
    mismagent-create-contract|mismagent-seam-cross-deploy)
      $WITH_CROSS || continue ;;
  esac
  rm -rf "$TARGET/.agents/skills/$name"
  cp -R "$d" "$TARGET/.agents/skills/$name"
done
cp "$HERE"/agents/*.toml "$TARGET/.codex/agents/"

if [ -f "$TARGET/AGENTS.md" ]; then
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.mismagent.md"
  echo "AGENTS.md already exists -> wrote AGENTS.mismagent.md (merge it into yours)."
else
  cp "$HERE/AGENTS.md" "$TARGET/AGENTS.md"
fi
echo "mismAgent (Codex) installed into $TARGET — verify with /skills (expect mismagent-explore)."
"""


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    print("generating codex/ from plugins/ ...")
    convert_skills(KERNEL)
    convert_skills(CROSS, cross=True)
    convert_agents()
    convert_commands()
    copy_profile_templates()
    convert_methodology()
    write(os.path.join(OUT, "install.sh"), INSTALL_SH)
    os.chmod(os.path.join(OUT, "install.sh"), 0o755)
    print("done.")


if __name__ == "__main__":
    main()
