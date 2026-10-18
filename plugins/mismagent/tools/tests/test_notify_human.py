"""Tests for hooks/notify-human.py — stdlib unittest; feeds a Stop event on stdin, with
MISMAGENT_NOTIFY pointed at a script that records what would be notified.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "hooks", "notify-human.py")


class NotifyHuman(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = os.path.join(self.dir, "notified.log")
        self.recorder = os.path.join(self.dir, "record.sh")
        with open(self.recorder, "w") as f:
            f.write('#!/bin/sh\nprintf "%%s|%%s\\n" "$1" "$2" >> "%s"\n' % self.log)
        os.chmod(self.recorder, 0o755)
        self.session = uuid.uuid4().hex

    def tearDown(self):
        seen = os.path.join(tempfile.gettempdir(), "mismagent-notified-%s" % self.session)
        if os.path.exists(seen):
            os.remove(seen)

    def stop(self, **event):
        event.setdefault("session_id", self.session)
        event.setdefault("cwd", "/work/p7read")
        result = subprocess.run([sys.executable, HOOK], input=json.dumps(event), text=True,
                                capture_output=True, env=dict(os.environ, MISMAGENT_NOTIFY=self.recorder))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def notified(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return f.read().splitlines()

    def test_needs_human_is_notified_with_the_project(self):
        self.stop(last_assistant_message="ACTION: stuck 48\nNEXT: NEEDS-HUMAN: .mismagent/slices/48.md")
        self.assertEqual(self.notified(), ["mismAgent · p7read|NEEDS-HUMAN: .mismagent/slices/48.md"])

    def test_for_human_is_notified_too(self):
        self.stop(last_assistant_message="NEXT: start 49\nFOR-HUMAN: /mismagent:conventions — 2 proposals")
        self.assertEqual(self.notified(), ["mismAgent · p7read|FOR-HUMAN: /mismagent:conventions — 2 proposals"])

    def test_no_mark_no_notification(self):
        self.stop(last_assistant_message="ACTION: land 48\nNEXT: start 49")
        self.assertEqual(self.notified(), [])

    def test_once_per_wait(self):
        for _ in range(3):
            self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: confirm R3")
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: /mismagent:conventions")
        self.assertEqual(len(self.notified()), 2)

    def test_read_from_the_transcript(self):
        transcript = os.path.join(self.dir, "t.jsonl")
        with open(transcript, "w") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "NEXT: NEEDS-HUMAN: confirm R2"}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": "ok"}}) + "\n")
        self.stop(transcript_path=transcript)
        self.assertEqual(self.notified(), ["mismAgent · p7read|NEEDS-HUMAN: confirm R2"])

    def test_bad_input_never_fails(self):
        result = subprocess.run([sys.executable, HOOK], input="not json", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.stop(transcript_path="/nowhere.jsonl")
        self.assertEqual(self.notified(), [])


if __name__ == "__main__":
    unittest.main()
