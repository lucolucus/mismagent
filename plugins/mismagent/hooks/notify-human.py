#!/usr/bin/env python3
"""Stop hook: when the conductor's last message stops for the human (a `NEEDS-HUMAN:` line) or
tells them something while the flow goes on (`FOR-HUMAN:`), a desktop notification says so — under
/loop the line alone scrolls by unseen. Once per wait: a line already notified in this session is
not notified again until the wait ends (a report with an `ACTION:` line and no mark); every new
line of a report is. MISMAGENT_NOTIFY, if set, is a command run with the title and the message as
its two arguments instead of the desktop notification (e.g. a script that pushes to the phone).
Never blocks: the notifier's output never reaches Claude Code, and every failure is silent (a line
not delivered is tried again at the next stop).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# a mark at the start of a line, after an optional bullet, `NEXT:` and markdown emphasis
MARK = re.compile(r"^[\s>*_`-]*(?:NEXT:\s*[`*_]*)?((?:NEEDS|FOR)-HUMAN:.*)$")
ACTION = re.compile(r"^[\s*_`]*ACTION:")


def human_turn(entry):
    """A message the human typed (not a tool result, which the transcript also files as `user`)."""
    content = (entry.get("message") or {}).get("content")
    return isinstance(content, str) or any(
        isinstance(c, dict) and c.get("type") == "text" for c in content or [])


def last_assistant_text(event):
    text = event.get("last_assistant_message")
    if isinstance(text, str):
        return text
    try:
        with open(event.get("transcript_path") or "", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return ""
    for line in reversed(lines):  # this turn only: an earlier turn's wait is not this stop's
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "user" and human_turn(entry):
            return ""
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content") or []
        if isinstance(content, str):
            return content
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def marked(text):
    found = []
    for line in text.splitlines():
        m = MARK.match(line)
        if m:
            found.append(m.group(1).strip(" `*_"))
    return found


def seen_path(session):
    return os.path.join(tempfile.gettempdir(), "mismagent-notified-%s" % (session or "none"))


def digest(line):
    return hashlib.sha1(line.encode("utf-8")).hexdigest()


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return set(f.read().split())
    except OSError:
        return set()


def save(path, digests):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(digests)))


def notify(title, message):
    """True when the notifier ran and succeeded; its output is swallowed."""
    custom = os.environ.get("MISMAGENT_NOTIFY")
    if custom:
        cmd = [custom, title, message]
    elif sys.platform == "darwin":
        cmd = ["osascript", "-e", "on run argv", "-e",
               "display notification (item 2 of argv) with title (item 1 of argv) sound name \"Glass\"",
               "-e", "end run", title, message]
    elif shutil.which("notify-send"):
        cmd = ["notify-send", title, message]
    else:
        return False
    try:
        return subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


try:
    event = json.load(sys.stdin)
    text = last_assistant_text(event)
    lines = marked(text)
    path = seen_path(event.get("session_id"))
    if not lines:
        if any(ACTION.match(l) for l in text.splitlines()) and os.path.exists(path):
            os.remove(path)  # an action ran: the wait is over, its line may come back
    else:
        seen = load(path)
        new = [l for l in dict.fromkeys(lines) if digest(l) not in seen]
        project = os.path.basename(os.path.normpath(event.get("cwd") or os.getcwd()))
        if new and notify("mismAgent · %s" % project, " · ".join(new)[:300]):
            save(path, seen | {digest(l) for l in new})
except Exception:  # a notification never stops the flow
    pass
sys.exit(0)
