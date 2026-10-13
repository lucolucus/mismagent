---
description: 'mismAgent: a read-only picture of the project in the browser — releases as swimlanes, requirements → examples → slices → tests, conventions, decisions. Usage: /mismagent:site'
---

# /mismagent:site — the project at a glance

Run `python3 "${CLAUDE_PLUGIN_ROOT}/tools/mmsite.py" --serve --open` from the project: it starts
the project's page server (or finds it running), opens the page and prints its URL. The page follows
the project live; the server never moves state and stops after half an hour unwatched.

Reply with the URL and one line of counts (slices done, examples tested, what `mm` says is next). If the script fails, show its message; do not
work around it.
