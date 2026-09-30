#!/usr/bin/env python3
"""prompt_budget.py — the prompt diet, enforced (Python 3 stdlib only).

Reads budgets.json beside this file: a word cap per operative prompt file (every skill, agent,
command, methodology file and PROFILE.md of the plugin), a cap on their total, a separate total
cap for the skills' references/ plus a cap on each reference file, and a cap on every frontmatter
`description` (characters).
Words = whitespace-separated tokens of the whole file (as `wc -w`). A capped file that does not
exist yet is "not yet written" (listed, not an error); an operative file with no cap is an error.
Usage: python3 prompt_budget.py  → JSON report; exit 1 if any cap is exceeded.
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
REFERENCES = ("plugins/*/skills/*/references/*.md",)
FRONTMATTER = ("plugins/*/skills/*/SKILL.md", "plugins/*/agents/*.md", "plugins/*/commands/*.md")


def files(patterns):
    return sorted({os.path.relpath(p, REPO) for g in patterns for p in glob.glob(os.path.join(REPO, g))})


def words(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return len(f.read().split())


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


def load_budgets():
    with open(os.path.join(TOOLS, "budgets.json"), encoding="utf-8") as f:
        return json.load(f)


def report(b=None):
    """{files: {rel: (words, cap)}, not_yet_written: [rel], total, references_total,
    violations: [(where, message)]}."""
    b = b or load_budgets()
    caps, out, bad = b["files"], {}, []
    for rel in files(OPERATIVE):
        n, cap = words(rel), caps.get(rel)
        out[rel] = (n, cap)
        if cap is None:
            bad.append((rel, "%d words, no budget in budgets.json (add one: no unbudgeted prompt)" % n))
        elif n > cap:
            bad.append((rel, "%d words > budget %d (over by %d)" % (n, cap, n - cap)))
    pending = sorted(set(caps) - set(out))  # capped, not yet written: the budget waits for it
    total = sum(n for n, _ in out.values())
    if total > b["total"]:
        bad.append(("<total>", "%d words > total budget %d" % (total, b["total"])))
    ref_words = {r: words(r) for r in files(REFERENCES)}
    exceptions = b.get("references_file_exceptions", {})
    for rel, n in ref_words.items():
        cap = exceptions.get(rel, b["references_file"])
        if n > cap:
            bad.append((rel, "%d words > per-reference budget %d" % (n, cap)))
    for rel in sorted(set(exceptions) - set(ref_words)):
        bad.append((rel, "reference exception but not found (update budgets.json)"))
    refs = sum(ref_words.values())
    if refs > b["references_total"]:
        bad.append(("<references>", "%d words > references budget %d" % (refs, b["references_total"])))
    for rel in files(FRONTMATTER):
        try:
            d = description(rel)
        except FrontmatterError as e:
            bad.append((rel, "unreadable frontmatter: %s" % e))
            continue
        if not d:
            bad.append((rel, "no description in the frontmatter"))
        elif len(d) > b["description_chars"]:
            bad.append((rel, "description %d chars > %d" % (len(d), b["description_chars"])))
    return {"files": out, "not_yet_written": pending, "total": total, "total_budget": b["total"], "references_total": refs,
            "references_budget": b["references_total"], "violations": bad}


def main():
    r = report()
    print(json.dumps({"total": r["total"], "total_budget": r["total_budget"],
                      "references_total": r["references_total"], "references_budget": r["references_budget"],
                      "not_yet_written": r["not_yet_written"],
                      "violations": ["%s: %s" % v for v in r["violations"]]}, indent=2))
    return 1 if r["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
