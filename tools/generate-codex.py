#!/usr/bin/env python3
"""
generate-codex.py — derive the Codex/OpenAI packaging of mismAgent from the Claude Code plugin.

The Claude plugin (plugins/mismagent + plugins/mismagent-cross-deploy) is the ONLY source of
truth; codex/ is a GENERATED view (the methodology's derived-view rule: a derived view regenerated from a source,
never hand-maintained). Do not edit codex/ by hand — edit the plugin, then re-run this script.

Mapping (verified against developers.openai.com/codex, 2026-07):
  plugin skill  SKILL.md (+ references/) -> codex/skills/mismagent-<name>/        (.agents/skills)
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


COMPOSER_DIR = ".agents/skills/mismagent-worker-composer"


# ---- text adaptation (deterministic, reviewable rules) -----------------------
def adapt(text):
    """Claude-Code idioms -> Codex idioms."""
    # module-namespaced command first (more specific than the generic rule)
    text = text.replace("/mismagent-cross-deploy:create-contract", "$mismagent-create-contract")
    # Codex has no thin agent commands: an agent is a subagent spawned by name
    text = text.replace("each agent's thin command (`/mismagent:<name>`)",
                        "each agent as a subagent (*\"spawn `mismagent-<name>`\"*)")
    agents = sorted(fn[len("mismagent-"):-3] for fn in os.listdir(os.path.join(KERNEL, "agents"))
                    if fn.startswith("mismagent-") and fn.endswith(".md"))
    text = re.sub(r"`?/mismagent:(%s)(?![a-z0-9-])`?" % "|".join(agents), r"the `mismagent-\1` subagent", text)
    text = re.sub(r"/mismagent:([a-z0-9-]+)", r"$mismagent-\1", text)
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/board.py"',
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/board.py",
                        ".agents/skills/mismagent-board/scripts/board.py")
    text = text.replace('"$CLAUDE_PLUGIN_ROOT/tools/mismagent.py"', COMPOSER_DIR + "/scripts/mismagent.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/mismagent.py", COMPOSER_DIR + "/scripts/mismagent.py")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/CLI.md", COMPOSER_DIR + "/references/CLI.md")
    text = text.replace("$CLAUDE_PLUGIN_ROOT/tools/LOOP.md", COMPOSER_DIR + "/references/LOOP.md")
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


# Bash for running checks, never for writing: the verifier stays read-only.
READ_ONLY = ("mismagent-verifier",)


def convert_agents():
    for fn in sorted(os.listdir(os.path.join(KERNEL, "agents"))):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(KERNEL, "agents", fn), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        name = fm["name"]
        tools = fm.get("tools", "")
        writes = any(t in tools for t in ("Bash", "Write", "Edit"))
        sandbox = "workspace-write" if writes and name not in READ_ONLY else "read-only"
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
  spawn is a fresh, independent session — exactly the fresh-context guarantee the review relies on.
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
  3. each row's `result_json` is the worker handoff → route it to step 4 as usual.
- **Concurrency/config:** the global `[agents]` settings gate this (`max_threads` default 6,
  `max_depth` 1 — you run in the main thread, so depth is never exceeded). Keep the profile's
  `build.max_parallel_workers` ≤ `max_threads`.
- **Model routing on Codex:** the tiers bind to reasoning effort by default — `light → low`,
  `standard → medium`, `deep → high` (the profile's `build.model_routing.tiers` may name a model
  instead). A CSV wave mixes tiers, so **split it: one `spawn_agents_on_csv` call per tier**, each
  passing that tier's model/effort if the spawn accepts one. When a spawn takes no per-call
  model/effort, the agent's TOML `model_reasoning_effort` applies: write `model=default` in the
  ledger line, never the tier's binding you could not apply.
"""


def convert_commands():
    for cmd, skill in (("worker-composer", "worker-composer"), ("board", "board"),
                       ("model", "model")):
        with open(os.path.join(KERNEL, "commands", "%s.md" % cmd), encoding="utf-8") as f:
            fm, body = parse_frontmatter(f.read())
        if cmd == "worker-composer":
            body = body.rstrip() + "\n" + COMPOSER_CODEX_NOTES
        emit_skill(skill, fm.get("description", ""), body)
    shutil.copy(os.path.join(KERNEL, "tools", "board.py"),
                _ensured(os.path.join(OUT, "skills", "mismagent-board", "scripts", "board.py")))
    print("  wrote codex/skills/mismagent-board/scripts/board.py")
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
        print("  wrote codex/skills/mismagent-worker-composer/%s/%s" % (sub, src))


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
    "**Setup (once).** From the mismagent repo: `codex/install.sh <your-project-root>` "
    "(add `--with-cross-deploy` only if boundaries cross deploy units). It copies the skills "
    "into `<project>/.agents/skills/`, the subagents into `<project>/.codex/agents/`, and this "
    "file as the project's `AGENTS.md` (or `AGENTS.mismagent.md` if one already exists — merge it). "
    "Verify: `/skills` lists `mismagent-explore`."
)

CODEX_LEGEND = (
    "\n> **Codex mapping (this packaging).** `[skill]`/`[command]` steps are Codex **skills** — "
    "invoke with `$mismagent-<name>` (or `/skills`). `[agent]` steps are Codex **subagents** in "
    "`.codex/agents/` — ask Codex to *\"spawn `mismagent-<name>` on <input>\"* (Codex spawns them "
    "only on explicit request). Skill names carry the `mismagent-` "
    "prefix because Codex has no namespaces. The board script lives at "
    "`.agents/skills/mismagent-board/scripts/board.py`. Subagents ship with a tuned "
    "`model_reasoning_effort` (challenger/verifier/architect: high) and a `sandbox_mode` matching "
    "their role (challenger, verifier: read-only). The worker-composer's parallel waves map onto "
    "`spawn_agents_on_csv` (see its skill's Codex execution notes); the `[agents]` config "
    "(`max_threads`, default 6) is the concurrency cap.\n"
)


def convert_methodology():
    """The methodology ships WHOLE (no paragraph surgery): its H1 is replaced by the Codex header,
    setup and legend; the rest is adapted like any other file."""
    path = os.path.join(KERNEL, "methodology", "mismagent.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("# "):
        sys.exit("%s must start with its '# ' title line — generate-codex.py replaces it" % path)
    body = adapt(text.split("\n", 1)[1] if "\n" in text else "")
    header = ("# mismAgent — Codex packaging\n\n" + GENERATED_NOTE + CODEX_LEGEND + "\n" + CODEX_SETUP + "\n")
    write(os.path.join(OUT, "AGENTS.md"), header + body)


# ---- the generated tree must be self-contained ---------------------------------
CLAUDE_ONLY = ("$CLAUDE_PLUGIN_ROOT", "redesign/composer-spec", "/plugin marketplace", "/mismagent:",
               "/mismagent-cross-deploy:")


def check_tree():
    """Fail loudly on a Claude-only idiom left in the output, a relative Markdown link, a
    `.agents/skills/...` path or a skill's `references/<file>` that does not resolve in codex/."""
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
            bad += ["%s: $mismagent-%s is no shipped skill" % (rel, n) for n in re.findall(r"\$mismagent-([a-z0-9-]+)", text)
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
        sys.exit("generated codex/ is not self-contained:\n  " + "\n  ".join(bad))


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
    check_tree()
    print("done.")


if __name__ == "__main__":
    main()
