#!/usr/bin/env python3
"""Stop hook: when the conductor's last message stops for the human (a `NEEDS-HUMAN:` line), a
desktop notification says so — under /loop the line alone scrolls by unseen. Once per wait: the
same line in the same session is not notified twice. MISMAGENT_NOTIFY, if set, is a command run
with the title and the message as its two arguments instead of the desktop notification (e.g. a
script that pushes to the phone). Never blocks: every failure is silent.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

MARK = "NEEDS-HUMAN:"


def last_assistant_text(event):
    text = event.get("last_assistant_message")
    if isinstance(text, str):
        return text
    try:
        with open(event.get("transcript_path") or "", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content") or []
        if isinstance(content, str):
            return content
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def needs_human(text):
    for line in text.splitlines():
        at = line.find(MARK)
        if at >= 0:
            return line[at:].strip(" `*")
    return None


def first_time(session, message):
    digest = hashlib.sha1(message.encode("utf-8")).hexdigest()
    seen = os.path.join(tempfile.gettempdir(), "mismagent-notified-%s" % (session or "none"))
    try:
        with open(seen, encoding="utf-8") as f:
            if f.read().strip() == digest:
                return False
    except OSError:
        pass
    with open(seen, "w", encoding="utf-8") as f:
        f.write(digest)
    return True


def notify(title, message):
    custom = os.environ.get("MISMAGENT_NOTIFY")
    if custom:
        subprocess.run([custom, title, message], timeout=10, check=False)
    elif sys.platform == "darwin":
        subprocess.run(["osascript", "-e", "on run argv", "-e",
                        "display notification (item 2 of argv) with title (item 1 of argv) sound name \"Glass\"",
                        "-e", "end run", title, message], timeout=10, check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], timeout=10, check=False)


try:
    event = json.load(sys.stdin)
    message = needs_human(last_assistant_text(event))
    if message and first_time(event.get("session_id"), message):
        project = os.path.basename(os.path.normpath(event.get("cwd") or os.getcwd()))
        notify("mismAgent · %s" % project, message[:200])
except Exception:  # a notification never stops the flow
    pass
sys.exit(0)
