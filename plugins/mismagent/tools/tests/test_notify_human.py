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

    def test_the_same_wait_again_after_an_action(self):
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: .mismagent/slices/doing/48.md")
        self.stop(last_assistant_message="still waiting")
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: .mismagent/slices/doing/48.md")
        self.stop(last_assistant_message="ACTION: build 48\nDONE: built\nNEXT: review")
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: .mismagent/slices/doing/48.md")
        self.assertEqual(len(self.notified()), 2)

    def test_every_new_line_of_a_report(self):
        self.stop(last_assistant_message="ACTION: land 48\nFOR-HUMAN: a\nFOR-HUMAN: b")
        self.stop(last_assistant_message="ACTION: land 49\nFOR-HUMAN: a\nFOR-HUMAN: c")
        self.assertEqual([n.split("|")[1] for n in self.notified()],
                         ["FOR-HUMAN: a · FOR-HUMAN: b", "FOR-HUMAN: c"])

    def test_prose_mentioning_the_mark_is_not_a_wait(self):
        self.stop(last_assistant_message="There is no NEEDS-HUMAN: line here.")
        self.assertEqual(self.notified(), [])

    def test_a_failed_delivery_is_tried_again(self):
        with open(self.recorder, "a") as f:
            f.write('[ -e "%s.ok" ] || exit 1\n' % self.log)
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: confirm R2")
        open(self.log + ".ok", "w").close()
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: confirm R2")
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: confirm R2")
        self.assertEqual(len(self.notified()), 2)  # the recorder logs before it fails

    def test_the_notifier_output_never_reaches_claude(self):
        with open(self.recorder, "a") as f:
            f.write('echo \'{"decision": "block", "reason": "x"}\'\n')
        self.stop(last_assistant_message="NEXT: NEEDS-HUMAN: confirm R2")  # stop() asserts no stdout

    def test_an_earlier_turn_is_not_this_stop(self):
        transcript = os.path.join(self.dir, "t.jsonl")
        with open(transcript, "w") as f:
            for entry in ({"type": "assistant", "message": {"content": [{"type": "text", "text": "NEEDS-HUMAN: old"}]}},
                          {"type": "user", "message": {"content": "my answer"}},
                          {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}):
                f.write(json.dumps(entry) + "\n")
        self.stop(transcript_path=transcript)
        self.assertEqual(self.notified(), [])

    def test_read_from_the_transcript(self):
        transcript = os.path.join(self.dir, "t.jsonl")
        with open(transcript, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "/mismagent:build"}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "NEXT: NEEDS-HUMAN: confirm R2"}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "ok"}]}}) + "\n")
        self.stop(transcript_path=transcript)
        self.assertEqual(self.notified(), ["mismAgent · p7read|NEEDS-HUMAN: confirm R2"])

    def test_bad_input_never_fails(self):
        result = subprocess.run([sys.executable, HOOK], input="not json", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.stop(transcript_path="/nowhere.jsonl")
        self.assertEqual(self.notified(), [])


if __name__ == "__main__":
    unittest.main()
