---
description: 'mismAgent: a read-only picture of the project in the browser — releases as swimlanes, requirements → examples → slices → tests, conventions, decisions. Usage: /mismagent:site'
---

# /mismagent:site — the project at a glance

Run `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mmsite.py" --open` from the project. It reads
`.mismagent/`, the acceptance tests and git, writes one self-contained HTML page to a temp file,
opens it, and prints its path. It never moves state and never writes inside the repository.

Reply with the path and one line from the page's own counts (slices done of the total, examples
with an acceptance test, what `mm` says is next). If the script fails, show its message; do not
work around it.
