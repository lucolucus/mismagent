"""Unit tests for bench/cost.py on small synthetic transcripts in temp dirs (never real ones)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cost  # noqa: E402

SESSION = "s1"
MANIFEST = """feature: feat
profile: x
blocks:
  - id: "kernel"
    type: "aggregate"
    wave: 1
    acceptance:
      - id: "AC1"
  - id: "kernel-pl"
    wave: 2
  - id: "unused-block"
    wave: 2
boundaries:
  - id: "not-a-block"
"""


def usage(i=0, cw=0, cr=0, o=0):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
            "output_tokens": o}


def assistant(mid, u, model="claude-opus-x", text=None, handback=None):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if handback:
        content.append({"type": "tool_use", "name": "SubagentHandback", "input": {"message": handback}})
    return {"type": "assistant", "message": {"id": mid, "model": model, "usage": u, "content": content}}


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        os.makedirs(os.path.join(self.dir, SESSION, "subagents"))
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def write_lines(self, path, lines):
        with open(path, "w", encoding="utf-8") as f:
            for o in lines:
                f.write(json.dumps(o) + "\n")

    def main_session(self, lines):
        self.write_lines(os.path.join(self.dir, SESSION + ".jsonl"), lines)

    def agent(self, agent_type, prompt, calls, description="", **meta):
        """calls: list of (message id, usage) or ready-made assistant lines."""
        self.n += 1
        base = os.path.join(self.dir, SESSION, "subagents", "agent-a%02d" % self.n)
        lines = [user(prompt)] + [c if isinstance(c, dict) else assistant(*c) for c in calls]
        self.write_lines(base + ".jsonl", lines)
        with open(base + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(dict(agentType=agent_type, description=description, **meta), f)

    def manifest(self):
        p = os.path.join(self.dir, "building-blocks.yaml")
        with open(p, "w", encoding="utf-8") as f:
            f.write(MANIFEST)
        return p


class DedupeTest(Base):
    def test_repeated_message_id_counted_once(self):
        u = usage(1, 10, 100, 5)
        self.agent("mismagent:mismagent-worker", "go", [("m1", u), ("m1", u), ("m2", u)])
        rep = cost.report(self.dir)
        w = rep["kinds"]["mismagent:mismagent-worker"]
        self.assertEqual(w["calls"], 2)
        self.assertEqual(w["tokens"], {"input": 2, "cache_write": 20, "cache_read": 200, "output": 10, "total": 232})

    def test_streamed_repeat_keeps_final_usage(self):
        self.agent("mismagent:mismagent-worker", "go", [("m1", usage(cr=50, o=1)), ("m1", usage(cr=50, o=100))])
        self.agent("fork", "child", [("m1", usage(cr=50, o=1))], isFork=True, spawnDepth=2)
        rep = cost.report(self.dir)
        w = rep["kinds"]["mismagent:mismagent-worker"]
        self.assertEqual((w["calls"], w["tokens"]["output"], w["tokens"]["cache_read"]), (1, 100, 50))
        self.assertEqual(rep["kinds"]["fork"]["calls"], 0)
        self.assertEqual(rep["totals"]["tokens"]["total"], 150)

    def test_fork_replay_not_double_counted(self):
        self.agent("general-purpose", "parent", [("p1", usage(o=7))])
        self.agent("fork", "child", [("p1", usage(o=7)), ("f1", usage(o=3))], isFork=True, spawnDepth=2)
        rep = cost.report(self.dir)
        self.assertEqual(rep["kinds"]["general-purpose"]["tokens"]["output"], 7)
        self.assertEqual(rep["kinds"]["fork"]["tokens"]["output"], 3)
        self.assertEqual(rep["totals"]["tokens"]["output"], 10)

    def test_main_session_counted_separately(self):
        self.main_session([user("/build"), assistant("x1", usage(o=4)), assistant("x1", usage(o=4))])
        self.agent("mismagent:mismagent-worker", "go", [("w1", usage(o=1))])
        rep = cost.report(self.dir)
        self.assertEqual(rep["main"]["tokens"]["output"], 4)
        self.assertEqual(rep["totals"]["tokens"]["output"], 5)
        self.assertEqual(rep["sessions"], [SESSION])

    def test_session_filter(self):
        self.agent("mismagent:mismagent-worker", "go", [("w1", usage(o=1))])
        rep = cost.report(self.dir, sessions=["other"])
        self.assertEqual(rep["kinds"], {})
        self.assertIn("n/a", rep["workers"])


class KindTest(Base):
    def test_code_review_skill_prompt(self):
        self.agent("general-purpose", "Invoke the Skill `mismagent:code-review` on block kernel", [("a", usage(o=1))])
        self.agent("general-purpose", "Load the skill code-review and review", [("b", usage(o=1))])
        self.agent("mismagent:mismagent-verifier", "Verify; add the code-review lenses", [("c", usage(o=1))])
        self.agent("general-purpose", "Something else", [("d", usage(o=1))])
        kinds = cost.report(self.dir)["kinds"]
        self.assertEqual(kinds["code-review"]["dispatches"], 2)
        self.assertEqual(kinds["mismagent:mismagent-verifier"]["dispatches"], 1)
        self.assertEqual(kinds["general-purpose"]["dispatches"], 1)


class QuartileTest(Base):
    def test_quartiles_by_turns(self):
        # 8 worker sessions with 1..8 turns; each call 100 cache_read tokens, context grows with turns.
        for n in range(1, 9):
            self.agent("mismagent:mismagent-worker", "go",
                       [("w%d-%d" % (n, t), usage(cr=100 * (t + 1))) for t in range(n)])
        w = cost.report(self.dir)["workers"]
        self.assertEqual(w["sessions"], 8)
        self.assertEqual(w["median_turns"], 4.5)
        self.assertEqual([q["turns"] for q in w["quartiles"]], [[1, 2], [3, 4], [5, 6], [7, 8]])
        self.assertEqual(w["quartiles"][3]["median_turns"], 7.5)
        self.assertEqual(w["quartiles"][0]["median_final_context"], 150)  # final ctx 100 and 200
        total = sum(100 * (t + 1) for n in range(1, 9) for t in range(n))
        top = sum(100 * (t + 1) for n in (7, 8) for t in range(n))
        self.assertEqual(w["tokens"]["total"], total)
        self.assertAlmostEqual(w["longest_quartile_share"]["tokens"], round(top / total, 4))
        self.assertEqual(w["quartiles"][3]["tokens_per_call"], round(top / 15))
        self.assertNotIn("cost_usd", w)


class BlockTest(Base):
    def test_manifest_parse(self):
        blocks = cost.parse_manifest(self.manifest())
        self.assertEqual([b["id"] for b in blocks], ["kernel", "kernel-pl", "unused-block"])
        self.assertEqual(blocks[1]["wave"], "2")
        self.assertEqual(blocks[0]["feature"], "feat")

    def test_attribution_and_checkpoints(self):
        self.agent("mismagent:mismagent-worker", "Realize `kernel-pl`; it consumes kernel.",
                   [("a", usage(o=10))], description="Realize kernel-pl")
        self.agent("mismagent:mismagent-worker", "Resume kernel-pl.\n\n## Checkpoint\n- AC1 done",
                   [assistant("b", usage(o=20), handback="RESULT: READY-FOR-REVIEW")])
        self.agent("mismagent:mismagent-worker", "Realize kernel",
                   [assistant("c", usage(o=5), handback="RESULT: CHECKPOINT\nnext: AC2")])
        self.agent("mismagent:mismagent-verifier", "Verify kernel", [("d", usage(o=1))],
                   description="Verify kernel")
        self.agent("general-purpose", "Spike: pick a library", [("e", usage(o=100))])
        rep = cost.report(self.dir, manifests=[self.manifest()])
        b = rep["blocks"]
        self.assertEqual(b["feat/kernel-pl"]["worker_sessions"], 2)
        self.assertEqual(b["feat/kernel-pl"]["checkpoints"], 0)
        self.assertEqual(b["feat/kernel-pl"]["resumed_from_checkpoint"], 1)
        self.assertEqual(b["feat/kernel-pl"]["tokens"]["total"], 30)
        self.assertEqual(b["feat/kernel"]["dispatches"],
                         {"mismagent:mismagent-verifier": 1, "mismagent:mismagent-worker": 1})
        self.assertEqual(b["feat/kernel"]["checkpoints"], 1)
        self.assertEqual((rep["checkpoints"], rep["resumed_from_checkpoint"]), (1, 1))
        self.assertEqual(b[cost.UNATTRIBUTED]["tokens"]["total"], 100)
        self.assertNotIn("feat/unused-block", b)
        s = rep["summary"]
        self.assertEqual((s["blocks_in_manifests"], s["blocks_with_dispatch"]), (3, 2))
        self.assertEqual(s["attributed_tokens"], 36)
        self.assertEqual(s["tokens_per_dispatched_block"], 18)
        self.assertNotIn("tokens_per_completed_block", s)
        self.assertNotIn("cost_per_dispatched_block_usd", s)
        self.assertEqual(set(rep["waves"]), {"feat/1", "feat/2"})

    def attribute(self, prompt, description=""):
        self.agent("mismagent:mismagent-worker", prompt, [("a%d" % self.n, usage(o=1))], description=description)
        return [k for k in cost.report(self.dir, manifests=[self.manifest()])["blocks"]]

    def test_explicit_target_beats_other_mentions(self):
        self.assertEqual(self.attribute("Build block `kernel` (aggregate).\nIt feeds kernel-pl and unused-block."),
                         ["feat/kernel"])

    def test_ambiguous_description_falls_to_target(self):
        self.assertEqual(self.attribute("Verify ONE block: `kernel-pl`\nalso kernel", "kernel vs kernel-pl"),
                         ["feat/kernel-pl"])

    def test_pack_path(self):
        self.assertEqual(self.attribute("Read packs/feat/unused-block.md then look at kernel and kernel-pl"),
                         ["feat/unused-block"])

    def test_ambiguous_prompt_is_unattributed(self):
        self.assertEqual(self.attribute("Fix batch: touches kernel and kernel-pl"), [cost.UNATTRIBUTED])

    def test_id_is_not_matched_inside_a_longer_word(self):
        self.assertEqual(self.attribute("Realize kernel-plus"), [cost.UNATTRIBUTED])

    def test_same_id_in_two_features_not_collapsed(self):
        other = os.path.join(self.dir, "other.yaml")
        with open(other, "w", encoding="utf-8") as f:
            f.write("feature: other\nblocks:\n  - id: kernel\n    wave: 1\n")
        self.agent("mismagent:mismagent-worker", "Build block `kernel`, feature other.", [("x", usage(o=1))])
        self.agent("mismagent:mismagent-worker", "Build block `kernel`.", [("y", usage(o=2))])
        rep = cost.report(self.dir, manifests=[self.manifest(), other])
        self.assertEqual(rep["summary"]["blocks_in_manifests"], 4)
        self.assertEqual(rep["summary"]["ids_in_several_features"], ["kernel"])
        self.assertEqual(rep["blocks"]["other/kernel"]["tokens"]["total"], 1)
        self.assertNotIn("feat/kernel", rep["blocks"])
        self.assertEqual(rep["blocks"][cost.UNATTRIBUTED]["tokens"]["total"], 2)

    def test_completed_blocks_from_feature_dir(self):
        fdir = os.path.join(self.dir, "features", "feat")
        os.makedirs(os.path.join(fdir, "integrated"))
        open(os.path.join(fdir, "integrated", "kernel.json"), "w").close()
        self.agent("mismagent:mismagent-worker", "Build block `kernel`", [("a", usage(o=10))])
        self.agent("mismagent:mismagent-worker", "Build block `kernel-pl`", [("b", usage(o=30))])
        rep = cost.report(self.dir, manifests=[self.manifest()], feature_dirs=[fdir])
        s = rep["summary"]
        self.assertEqual((s["blocks_with_dispatch"], s["blocks_completed"]), (2, 1))
        self.assertEqual(s["tokens_per_dispatched_block"], 20)
        self.assertEqual(s["tokens_per_completed_block"], 40)
        self.assertTrue(rep["blocks"]["feat/kernel"]["completed"])
        self.assertFalse(rep["blocks"]["feat/kernel-pl"]["completed"])
        with self.assertRaises(ValueError):  # a manifest feature without its feature dir
            cost.report(self.dir, manifests=[self.manifest()], feature_dirs=[os.path.join(self.dir, "x")])


class PriceTest(Base):
    PRICES = {"opus": {"input": 10, "cache_write": 20, "cache_read": 1, "output": 50}}

    def test_no_prices_no_cost_fields(self):
        self.agent("mismagent:mismagent-worker", "go", [("a", usage(1, 1, 1, 1))])
        rep = cost.report(self.dir, manifests=[self.manifest()])
        self.assertFalse(rep["priced"])
        self.assertNotIn("usd", json.dumps(rep).lower())

    def test_prices_give_cost(self):
        self.agent("mismagent:mismagent-worker", "Realize kernel",
                   [("a", usage(1_000_000, 1_000_000, 1_000_000, 1_000_000))])
        rep = cost.report(self.dir, manifests=[self.manifest()], prices=self.PRICES)
        self.assertEqual(rep["totals"]["cost_usd"], 81.0)
        self.assertEqual(rep["workers"]["cost_per_call_usd"], 81.0)
        self.assertEqual(rep["workers"]["longest_quartile_share"]["cost"], 1.0)
        self.assertEqual(rep["summary"]["cost_per_dispatched_block_usd"], 81.0)

    def test_missing_rate_is_na_or_rejected(self):
        self.agent("general-purpose", "x", [("a", usage(o=1_000_000, cr=5))])
        rep = cost.report(self.dir, prices={"opus": {"output": 50, "input": 1}})
        self.assertIn("cache_read", rep["totals"]["cost_usd"]["n/a"])
        rep = cost.report(self.dir, prices={"opus": {"output": 50, "cache_read": 1}})  # unused classes: fine
        self.assertEqual(rep["totals"]["cost_usd"], 50.0)
        with self.assertRaises(ValueError):
            cost.load_prices({"opus": {"output": 50}})
        with self.assertRaises(ValueError):
            cost.load_prices({"opus": {"input": 1, "cache_write": 1, "cache_read": "x", "output": 1}})
        self.assertEqual(cost.load_prices(self.PRICES), self.PRICES)

    def test_unpriced_model_is_na_not_partial(self):
        self.agent("general-purpose", "x", [assistant("a", usage(o=1_000_000), model="claude-sonnet-y")])
        rep = cost.report(self.dir, prices=self.PRICES)
        self.assertIn("n/a", rep["totals"]["cost_usd"])


class CliTest(Base):
    def test_markdown_and_json(self):
        self.agent("mismagent:mismagent-worker", "Realize kernel", [("a", usage(o=3))])
        for args, needle in ((["--md"], "## Worker sessions by turns"), ([], '"workers"')):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cost.main([self.dir, "--manifest", self.manifest()] + args), 0)
            self.assertIn(needle, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
