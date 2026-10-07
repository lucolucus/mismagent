"""
derived.py — what the Codex and pi generators share.

The Claude Code plugin (plugins/mismagent) is the ONLY source of truth; codex/ and pi/ are
GENERATED views of it. This module holds the runtime-neutral part of the derivation: reading the
plugin, the adaptations every other runtime needs, shipping `mm.py`, the AGENTS.md body and the
self-containment check. Each generator adds its own idioms on top.

Every path into the shipped skills is written against SKILLS; the installer replaces it with the
ABSOLUTE skills directory of the installation, so a command works from any cwd.
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL = os.path.join(ROOT, "plugins", "mismagent")
SKILLS = "@@MISMAGENT_SKILLS@@"
MM = SKILLS + "/mismagent-build/scripts/mm.py"
PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
SOURCE_URL = "https://github.com/lucolucus/mismagent/blob/master/"

# Claude Code idioms that must not survive in a generated tree
CLAUDE_ONLY = ("CLAUDE_PLUGIN_ROOT", "CLAUDE.md", ".claude/", "/plugin marketplace", "/mismagent:",
               "/loop")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(out, rel, content, mode=None):
    path = os.path.join(out, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if mode:
        os.chmod(path, mode)
    print("  wrote %s" % os.path.relpath(path, ROOT))


def replaced(text, old, new, where):
    """Replace a passage the derivation depends on; fail loudly when the source no longer has it."""
    if old not in text:
        sys.exit("%s: expected passage not found, update the generator:\n  %r" % (where, old[:80]))
    return text.replace(old, new)


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


def plugin_skills():
    skills = os.path.join(KERNEL, "skills")
    return sorted(n for n in os.listdir(skills) if os.path.isfile(os.path.join(skills, n, "SKILL.md")))


def plugin_agents():
    return sorted(fn[:-3] for fn in os.listdir(os.path.join(KERNEL, "agents")) if fn.endswith(".md"))


def version():
    return json.loads(read(os.path.join(KERNEL, ".claude-plugin", "plugin.json")))["version"]


# ---- runtime-neutral adaptation -------------------------------------------------
def adapt_common(text):
    """What every other runtime needs: the installed paths, AGENTS.md for CLAUDE.md, the project's
    skills under .agents/skills/, the plugin's skills under their prefixed names."""
    text = text.replace(PLUGIN_ROOT + "/tools/mm.py", MM)
    text = re.sub(re.escape(PLUGIN_ROOT) + r"/skills/([a-z0-9-]+)/", SKILLS + r"/mismagent-\1/", text)
    text = text.replace("CLAUDE.md", "AGENTS.md")
    text = text.replace(".claude/skills/", ".agents/skills/")
    for name in plugin_skills():
        text = text.replace("`%s` skill" % name, "`mismagent-%s` skill" % name)
    return text


def without_loop(text, where):
    """The build's always-on mode is Claude Code's /loop: other runtimes call the build again."""
    start = text.find("**Under `/loop`**")
    if start == -1:
        sys.exit("%s: the /loop paragraph moved, update the generator" % where)
    end = text.find("\n\n", start)
    return text[:start] + text[end + 2:]


# ---- skills ---------------------------------------------------------------------------
def emit_skill(out, adapt, note, name, description, body):
    front = "---\nname: mismagent-%s\ndescription: %s\n---\n" % (name, json.dumps(adapt(description)))
    write(out, "skills/mismagent-%s/SKILL.md" % name, front + "\n" + note + "\n" + adapt(body))


def ship_skills(out, adapt, note):
    """Each plugin skill as mismagent-<name>, its references/ adapted beside it."""
    for name in plugin_skills():
        fm, body = parse_frontmatter(read(os.path.join(KERNEL, "skills", name, "SKILL.md")))
        emit_skill(out, adapt, note, name, fm.get("description", ""), body)
        refs = os.path.join(KERNEL, "skills", name, "references")
        for fn in sorted(os.listdir(refs)) if os.path.isdir(refs) else []:
            write(out, "skills/mismagent-%s/references/%s" % (name, fn), adapt(read(os.path.join(refs, fn))))


# ---- what ships beside the skills --------------------------------------------------
def ship_mm(out, adapt):
    """mm.py ships in the build skill's scripts/. Its messages and the files it reads are adapted
    like the prompts (AGENTS.md, .agents/skills/conventions, the runtime's command names)."""
    src = read(os.path.join(KERNEL, "tools", "mm.py"))
    for needle in ('"CLAUDE.md"', '".claude/skills/conventions"'):
        if needle not in src:
            sys.exit("mm.py no longer reads %s: update derived.ship_mm" % needle)
    write(out, "skills/mismagent-build/scripts/mm.py", adapt(src), 0o755)


def agents_md_body(adapt):
    """The plugin's README, adapted: what mismAgent is, the commands, what lives in a project."""
    text = read(os.path.join(KERNEL, "README.md"))
    where = "plugins/mismagent/README.md"
    text = text.split("\n", 1)[1]  # the generator writes its own title
    text = re.sub(r"\*\*Requires\*\* Claude Code.*?\n\n", "", text, flags=re.S)
    text = re.sub(r"Or leave `/loop .*?\n\n", "\n", text, flags=re.S)
    text = replaced(text, "`docs/rationale/v0.5-vision.md` at the repository root",
                    "[`v0.5-vision.md`](%sdocs/rationale/v0.5-vision.md)" % SOURCE_URL, where)
    text = re.sub(r"\n\| `hooks/` \|[^\n]*", "", text)
    text = re.sub(r"\nThe v0\.26 flow .*", "\n", text, flags=re.S)
    # the Contents table names the plugin's files: name the installed pieces instead
    text = re.sub(r"`skills/([a-z-]+)`", r"`mismagent-\1` skill", text)
    text = re.sub(r"`agents/(mismagent-[a-z-]+)`", r"`\1` agent", text)
    text = replaced(text, "`commands/build.md`", "`mismagent-build` skill", where)
    text = replaced(text, "`tools/mm.py`", "`mismagent-build/scripts/mm.py`", where)
    return adapt(text).rstrip() + "\n"


# ---- the generated tree must be self-contained ------------------------------------
def check_tree(out, skill_calls):
    """Fail on a Claude-only idiom left in the output, a skill call to no shipped skill, a relative
    link or an installed path that does not resolve. `skill_calls` matches the runtime's call."""
    bad = []
    for d, _, fns in os.walk(out):
        for fn in fns:
            if not fn.endswith((".md", ".toml", ".py")):
                continue
            path = os.path.join(d, fn)
            text, rel = read(path), os.path.relpath(path, ROOT)
            bad += ["%s: Claude-only idiom %r" % (rel, t) for t in CLAUDE_ONLY if t in text]
            bad += ["%s: %s calls no shipped skill" % (rel, n) for n in re.findall(skill_calls, text)
                    if not os.path.isdir(os.path.join(out, "skills", "mismagent-" + n))]
            for link in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
                if not re.match(r"^[a-z]+:", link) and not os.path.exists(os.path.join(d, link)):
                    bad.append("%s: link %s does not resolve" % (rel, link))
            for m in re.finditer(re.escape(SKILLS) + r"/([A-Za-z0-9_./-]+)", text):
                p = m.group(1).rstrip(".")
                if text[m.start() - 1:m.start()] not in ('"', "`"):
                    bad.append("%s: %s/%s is not quoted (a path may hold spaces)" % (rel, SKILLS, p))
                if "<" not in p and not os.path.exists(os.path.join(out, "skills", p)):
                    bad.append("%s: path %s/%s not shipped" % (rel, SKILLS, p))
            skill = re.match(r"skills/([^/]+)/", os.path.relpath(path, out))
            for p in re.findall(r"`references/([A-Za-z0-9_.-]+)`", text) if skill else []:
                if not os.path.exists(os.path.join(out, "skills", skill.group(1), "references", p)):
                    bad.append("%s: references/%s not shipped" % (rel, p))
    if bad:
        sys.exit("generated %s is not self-contained:\n  %s"
                 % (os.path.relpath(out, ROOT), "\n  ".join(bad)))


def fresh(out, argv, script):
    """The output directory: `--out DIR` for tests, else the default; emptied before generating."""
    if argv[1:2] == ["--out"] and len(argv) == 3:
        out = os.path.abspath(argv[2])
    elif argv[1:]:
        sys.exit("usage: %s [--out DIR]" % script)
    if os.path.isdir(out):
        shutil.rmtree(out)
    return out
