#!/usr/bin/env python3
"""prompt_budget.py — the prompt diet, enforced (Python 3 stdlib only).

Reads budgets.json beside this file: a word cap per operative prompt file (every skill, agent,
command, methodology file and PROFILE.md of the plugin), a cap on their total, a separate total
cap for the skills' references/, and a cap on every frontmatter `description` (characters).
Words = whitespace-separated tokens of the whole file (as `wc -w`).
Usage: python3 prompt_budget.py  → JSON report; exit 1 if any cap is exceeded.
"""
import glob
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(TOOLS)))
sys.path.insert(0, TOOLS)
import mismagent  # noqa: E402  (its YAML subset parses the frontmatter)

OPERATIVE = ("plugins/*/skills/*/SKILL.md", "plugins/*/agents/*.md", "plugins/*/commands/*.md",
             "plugins/*/methodology/*.md", "plugins/*/PROFILE.md")
REFERENCES = ("plugins/*/skills/*/references/*.md",)
FRONTMATTER = ("plugins/*/skills/*/SKILL.md", "plugins/*/agents/*.md", "plugins/*/commands/*.md")


def files(patterns):
    return sorted({os.path.relpath(p, REPO) for g in patterns for p in glob.glob(os.path.join(REPO, g))})


def words(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return len(f.read().split())


def description(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        text = f.read()
    end = text.find("\n---", 3) if text.startswith("---") else -1
    if end == -1:
        return None
    d = mismagent.parse_yaml(text[3:end]).get("description")
    return d if isinstance(d, str) else None


def load_budgets():
    with open(os.path.join(TOOLS, "budgets.json"), encoding="utf-8") as f:
        return json.load(f)


def report(b=None):
    """{files: {rel: (words, cap)}, total, references_total, violations: [(where, message)]}."""
    b = b or load_budgets()
    caps, out, bad = b["files"], {}, []
    for rel in files(OPERATIVE):
        n, cap = words(rel), caps.get(rel)
        out[rel] = (n, cap)
        if cap is None:
            bad.append((rel, "%d words, no budget in budgets.json (add one: no unbudgeted prompt)" % n))
        elif n > cap:
            bad.append((rel, "%d words > budget %d (over by %d)" % (n, cap, n - cap)))
    for rel in sorted(set(caps) - set(out)):
        bad.append((rel, "budgeted but not found (moved or deleted? update budgets.json)"))
    total = sum(n for n, _ in out.values())
    if total > b["total"]:
        bad.append(("<total>", "%d words > total budget %d" % (total, b["total"])))
    refs = sum(words(r) for r in files(REFERENCES))
    if refs > b["references_total"]:
        bad.append(("<references>", "%d words > references budget %d" % (refs, b["references_total"])))
    for rel in files(FRONTMATTER):
        try:
            d = description(rel)
        except mismagent.UsageError as e:
            bad.append((rel, "unreadable frontmatter: %s" % e))
            continue
        if not d:
            bad.append((rel, "no description in the frontmatter"))
        elif len(d) > b["description_chars"]:
            bad.append((rel, "description %d chars > %d" % (len(d), b["description_chars"])))
    return {"files": out, "total": total, "total_budget": b["total"], "references_total": refs,
            "references_budget": b["references_total"], "violations": bad}


def main():
    r = report()
    print(json.dumps({"total": r["total"], "total_budget": r["total_budget"],
                      "references_total": r["references_total"], "references_budget": r["references_budget"],
                      "violations": ["%s: %s" % v for v in r["violations"]]}, indent=2))
    return 1 if r["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
