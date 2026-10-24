#!/usr/bin/env python3
"""prompt_lint.py — what the prompts must get right (Python 3 stdlib only).

Every frontmatter of the plugin's skills, agents and commands is readable and has a `description`
of at most DESCRIPTION_CHARS characters (it is what Claude Code shows to choose a skill or an agent).
No word caps: what counts is that the prompts work, not how long they are (the user, 2026-10-24).
Usage: python3 prompt_lint.py  → JSON report; exit 1 on any violation.
"""
import glob
import json
import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(TOOLS)))

OPERATIVE = ("plugins/*/skills/*/SKILL.md", "plugins/*/agents/*.md", "plugins/*/commands/*.md",
             "plugins/*/methodology/*.md", "plugins/*/PROFILE.md")
DESCRIPTION_CHARS = 250
FRONTMATTER = ("plugins/*/skills/*/SKILL.md", "plugins/*/agents/*.md", "plugins/*/commands/*.md")


def files(patterns):
    return sorted({os.path.relpath(p, REPO) for g in patterns for p in glob.glob(os.path.join(REPO, g))})


class FrontmatterError(ValueError):
    pass


def description(rel):
    """The frontmatter `description:` value (single-line; plain, 'single' or "double" quoted)."""
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        text = f.read()
    end = text.find("\n---", 3) if text.startswith("---") else -1
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        m = re.match(r"^description:\s*(.*?)\s*$", line)
        if not m:
            continue
        v = m.group(1)
        if v[:1] in ("'", '"'):
            q = v[0]
            if len(v) < 2 or v[-1] != q:
                raise FrontmatterError("unterminated %s-quoted description" % q)
            v = v[1:-1].replace("''", "'") if q == "'" else v[1:-1].replace('\\"', '"')
        return v or None
    return None


def report():
    """{files: [rel], violations: [(where, message)]}."""
    bad = []
    for rel in files(FRONTMATTER):
        try:
            d = description(rel)
        except FrontmatterError as e:
            bad.append((rel, "unreadable frontmatter: %s" % e))
            continue
        if not d:
            bad.append((rel, "no description in the frontmatter"))
        elif len(d) > DESCRIPTION_CHARS:
            bad.append((rel, "description %d chars > %d" % (len(d), DESCRIPTION_CHARS)))
    return {"files": files(OPERATIVE), "violations": bad}


def main():
    r = report()
    print(json.dumps({"files": len(r["files"]), "violations": ["%s: %s" % v for v in r["violations"]]}, indent=2))
    return 1 if r["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
