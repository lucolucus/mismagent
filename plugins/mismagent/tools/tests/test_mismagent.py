"""Tests for tools/mismagent.py — stdlib unittest, temp git repos, no network.
Run: python3 -m unittest discover -s plugins/mismagent/tools/tests -v"""
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(TOOLS, "mismagent.py")
PLUGIN = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import mismagent  # noqa: E402

MANIFEST = """\
blocks:
  - id: scaffold-app
    type: scaffold
    context: shell
    wave: 0
  - id: agg-order          # the owner
    type: aggregate
    context: orders
    wave: 1
    release: R0
    related_adrs: [0001]
    invariants:
      - "[INV-1] an order total is never negative"
  - id: svc-order
    type: application-service
    context: orders
    wave: 2
    release: R0
    consumes: [b-order]
    commands: [PlaceOrder]
  - id: rm-orders
    type: read-model
    context: orders
    wave: 2
    release: R1
    consumes: [b-order]
    view_shape: { orderId: string, total: int }
  - id: svc-report
    type: application-service
    context: reports
    wave: 3
    release: R1
    consumes: [b-rm]
    commands: [BuildReport]
boundaries:
  - id: b-order
    owner: agg-order
    consumers: [svc-order, rm-orders]
    pinned_types: { OrderPlaced: "orderId:string · lines:[OrderLine]", OrderLine: "sku:string · qty:int" }
    contract_test: invariant-test
  - id: b-rm
    owner: rm-orders
    consumers: [svc-report]
    pinned_types: { OrderRow: "orderId:string · total:int" }
    contract_test: consumer-driven
releases:
  R0: { goal: "place an order", launch: "orders screen", blocks: [agg-order, svc-order] }
  R1: { goal: "report", launch: "report screen", blocks: [rm-orders, svc-report] }
"""
ROWS = [("scaffold-app", "scaffold", "shell", 0, None), ("agg-order", "aggregate", "orders", 1, "R0"),
        ("svc-order", "application-service", "orders", 2, "R0"), ("rm-orders", "read-model", "orders", 2, "R1"),
        ("svc-report", "application-service", "reports", 3, "R1")]
TASKS = {"agg-order": ["INV-1 a negative total is rejected"],
         "svc-order": ["PlaceOrder creates an order", "PlaceOrder with no lines is rejected"],
         "rm-orders": ["the list shows orderId and total"],
         "svc-report": ["BuildReport sums totals", "BuildReport on no orders is rejected"]}
CTX = {r[0]: r[2] for r in ROWS}


def block_file(bid, btype, ctx, wave, release=None, tasks=None, sources=True, what=True):
    fm = "---\nid: %s\ntype: %s\ncontext: %s\nwave: %s\n" % (bid, btype, ctx, wave)
    fm += ("release: %s\n" % release if release else "") + "---\n"
    return fm + "# %s\n\n## What to do\n%s\n\n## Tasks\n%s\n\n%s" % (
        bid, "Build it." if what else "", "\n".join("- " + t for t in (tasks or [])),
        "Sources: ADR-0001, tactical model\n" if sources else "")


def sh(cwd, *args):
    p = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError("%s failed: %s" % (args, p.stderr))
    return p.stdout.strip()


class Base(unittest.TestCase):
    """One project repo (tmp/proj) holding the feature dir; the integration line is feature/shop."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "proj")
        self.out = os.path.join(self.repo, ".mismagent")
        self.feat = os.path.join(self.out, "features", "shop")
        self.write_feature(MANIFEST)
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "config", "user.email", "t@example.com")
        sh(self.repo, "git", "config", "user.name", "t")
        self.put("README", "base\n", base=self.repo)
        sh(self.repo, "git", "add", ".")
        sh(self.repo, "git", "commit", "-q", "-m", "seed")
        sh(self.repo, "git", "branch", "feature/shop")

    def write_feature(self, manifest, skip=(), mutate=None):
        shutil.rmtree(os.path.join(self.feat, "blocks"), True)
        self.put("building-blocks.yaml", manifest)
        for bid, t, ctx, w, rel in ROWS:
            if bid not in skip:
                kw = dict({"tasks": TASKS.get(bid, [])}, **(mutate or {}).get(bid, {}))
                self.put("blocks/%s/todo/%s.md" % (ctx, bid), block_file(bid, t, ctx, w, rel, **kw))

    def put(self, rel, text, base=None):
        p = os.path.join(base or self.feat, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def run_tool(self, *args, expect=None, cwd=None):
        p = subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, text=True, cwd=cwd)
        if expect is not None:
            self.assertEqual(p.returncode, expect, p.stdout + p.stderr)
        try:
            return json.loads(p.stdout)
        except ValueError:
            return p.stdout

    def commit(self, wt, rel, text):
        self.put(rel, text, base=wt)
        sh(wt, "git", "add", rel)
        sh(wt, "git", "commit", "-q", "-m", "c " + rel)
        return sh(wt, "git", "rev-parse", "HEAD")

    def block_wt(self, bid):
        path = os.path.join(self.tmp, "wt", bid)
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "block/" + bid, path, "feature/shop")
        return path

    def line_commit(self, rel, text):
        path = os.path.join(self.tmp, "wt", "line")
        sh(self.repo, "git", "worktree", "add", "-q", path, "feature/shop")
        s = self.commit(path, rel, text)
        sh(self.repo, "git", "worktree", "remove", "--force", path)
        return s

    def move(self, bid, to):
        src = glob.glob(os.path.join(self.feat, "blocks", "*", "*", bid + ".md"))[0]
        dst = os.path.join(os.path.dirname(os.path.dirname(src)), to, bid + ".md")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)

    def spec_hash(self, bid):
        md = self.run_tool("pack", self.feat, bid, expect=0)
        return re.match(r"spec_hash: (\w+)\n", md).group(1)

    def review(self, bid, ref=None, h=None, expect=0):
        return self.run_tool("proof", "record", self.feat, "review", bid, "--sha", ref or "block/" + bid,
                             "--spec-hash", h or self.spec_hash(bid), expect=expect)

    def compose(self, op, bid, expect=None):
        extra = ["--integration", "feature/shop", "--branch", "block/" + bid] if op == "start" else []
        return self.run_tool("compose", op, self.feat, bid, *extra, expect=expect)

    def integrate(self, bid):
        wt = self.block_wt(bid)
        self.commit(wt, "src/%s.txt" % bid, bid + "\n")
        if bid != "scaffold-app":
            self.review(bid)
        self.compose("start", bid, expect=0)
        self.compose("promote", bid, expect=0)
        return wt

    def gaps(self):
        out = self.run_tool("lint", self.feat)
        return {(g["rule"], g["where"]) for g in out["gaps"]}, out


class TestYaml(unittest.TestCase):
    def test_apostrophe_is_text_unless_it_opens_a_scalar(self):
        doc = mismagent.parse_yaml("a: don't # a comment\nb: [don't, 'it''s']\nc: 'x # y'\n")
        self.assertEqual(doc, {"a": "don't", "b": ["don't", "it's"], "c": "x # y"})

    def test_block_scalars_preserved_literally(self):
        doc = mismagent.parse_yaml("k: |\n  line 'one'\n\n  # not a comment\n  - not a list\nf: >\n  a\n  b\n\n  c\nz: 1\n")
        self.assertEqual(doc["k"], "line 'one'\n\n# not a comment\n- not a list\n")
        self.assertEqual(doc["f"], "a b\nc\n")
        self.assertEqual(doc["z"], 1)


class TestLint(Base):
    def test_complete_manifest_passes(self):
        out = self.run_tool("lint", self.feat, expect=0)
        self.assertTrue(out["ok"])

    def test_log29_consumed_boundary_and_required_fields_missing(self):
        m = (MANIFEST.replace("consumes: [b-rm]", "consumes: [b-rm, b-ghost]")
             .replace("    contract_test: invariant-test\n", "")
             .replace('    pinned_types: { OrderRow: "orderId:string · total:int" }\n', ""))
        self.write_feature(m)
        gaps, out = self.gaps()
        self.assertFalse(out["ok"])
        for g in [("consumes.boundary", "svc-report"), ("boundary.contract_test", "b-order"),
                  ("boundary.pinned_types", "b-rm")]:
            self.assertIn(g, gaps)
        bounce = {g["rule"]: g["bounce_to"] for g in out["gaps"]}
        self.assertEqual((bounce["boundary.pinned_types"], bounce["consumes.boundary"]), ("architect", "build-manifest"))
        self.assertFalse(any(g["rule"].startswith("pins") for g in out["gaps"]))  # no type guessing

    def test_structural_gaps(self):
        m = (MANIFEST.replace("    wave: 3\n    release: R1\n", "    wave: 3\n")
             .replace("consumers: [svc-order, rm-orders]", "consumers: [svc-order]"))
        self.write_feature(m, skip=("rm-orders",), mutate={
            "agg-order": {"tasks": ["a total is checked"]},
            "svc-order": {"tasks": ["an order is created"], "sources": False}})
        self.put("blocks/orders/todo/stray.md", "---\nid: stray\n---\n")
        gaps, _ = self.gaps()
        for g in [("release.required", "svc-report"), ("blockfile.exists", "rm-orders"),
                  ("spec.invariants", "agg-order"), ("spec.commands", "svc-order"), ("spec.sources", "svc-order"),
                  ("boundary.consumers", "b-order")]:
            self.assertIn(g, gaps)
        self.assertIn("blockfile.orphan", {r for r, _ in gaps})

    def test_r0_has_no_wave_cap(self):  # R0 = the minimal slice the graph allows, at any depth
        m = (MANIFEST.replace("    wave: 3\n    release: R1", "    wave: 4\n    release: R0")
             .replace("    wave: 2\n    release: R1", "    wave: 3\n    release: R1"))
        self.write_feature(m)
        for bid, w in (("svc-report", 4), ("rm-orders", 3)):
            path = glob.glob(os.path.join(self.feat, "blocks", "*", "todo", bid + ".md"))[0]
            with open(path) as f:
                text = f.read()
            self.put(os.path.relpath(path, self.feat), re.sub(r"wave: \d+", "wave: %d" % w, text, count=1))
        self.run_tool("lint", self.feat, expect=0)

    def test_scaffold_declares_no_domain(self):
        m = MANIFEST.replace("    context: shell\n    wave: 0\n",
                             "    context: shell\n    wave: 0\n    invariants: [\"[INV-9] money is cents\"]\n")
        self.write_feature(m.replace("owner: rm-orders", "owner: scaffold-app"))
        texts = [g["gap"] for g in self.gaps()[1]["gaps"] if g["rule"] == "scaffold.domain_free"]
        self.assertEqual(len(texts), 1, texts)
        self.assertIn("invariants", texts[0])
        self.assertIn("owner of boundary b-rm", texts[0])

    def test_inv_tags_match_by_number(self):
        m = MANIFEST.replace('      - "[INV-1] an order total is never negative"\n',
                             '      - "[INV-1] an order total is never negative"\n      - "[INV-12] lines are unique"\n')
        self.write_feature(m, mutate={"agg-order": {"tasks": ["test_INV_12_duplicate_line_is_rejected"]}})
        gaps = [g["gap"] for g in self.gaps()[1]["gaps"] if g["rule"] == "spec.invariants"]
        self.assertEqual(gaps, ["invariant INV-1 has no criterion in ## Tasks"])  # INV-12 never counts as INV-1
        self.write_feature(m, mutate={"agg-order": {"tasks": ["inv 1: a negative total is rejected",
                                                               "test_INV_12_duplicate_line_is_rejected"]}})
        self.run_tool("lint", self.feat, expect=0)

    def test_wave_zero_and_frontmatter(self):
        self.write_feature(MANIFEST.replace("# the owner\n    type: aggregate\n    context: orders\n    wave: 1",
                                            "\n    type: aggregate\n    context: orders\n    wave: 0"))
        gaps, _ = self.gaps()
        self.assertIn(("wave.scaffold", "agg-order"), gaps)
        self.assertIn(("blockfile.frontmatter", "agg-order"), gaps)

    def test_central_spike_needs_node(self):
        self.put("context-map.md", "# Map\n\n## Open spikes\n- [ ] sync-spike: does sync hold?\n"
                 "      — owner: shop — central: true\n- [ ] other: q — owner: another — central: true\n", base=self.out)
        self.assertIn(("spikes.central_node", "sync-spike"), self.gaps()[0])
        self.put("tasks/be/backlog/sync-spike.md", "---\nid: sync-spike\ntype: spike\ncentral: true\n---\n")
        self.assertFalse({g for g in self.gaps()[0] if g[0].startswith("spikes")})

    def test_adr_checks_exist_unless_deferred(self):
        self.put("decisions/0001-money.md", "---\nscope: global\nstatus: accepted\nenforced_by:\n"
                 "  - check: checks/no-float.sh        # no from: the scaffold writes it\n"
                 "  - { check: checks/port-exists.sh, from: svc-order }\n---\n# 0001 — Money\n", base=self.out)
        out = self.run_tool("lint", self.feat, expect=0)  # scaffold open, svc-order not integrated
        self.assertEqual(sorted((d["file"], d["until"]) for d in out["deferred"] if d["file"].startswith("checks/")),
                         [("checks/no-float.sh", "the wave-0 scaffold is done"),
                          ("checks/port-exists.sh", "svc-order is integrated")])
        self.move("scaffold-app", "done")
        self.assertIn(("adr.checks", "decisions/0001-money.md"), self.gaps()[0])
        self.put("checks/no-float.sh", "#!/bin/sh\n", base=self.repo)
        self.run_tool("lint", self.feat, expect=0)
        self.put("integrated/svc-order.json", '{"id": "svc-order"}')
        gaps, out = self.gaps()
        self.assertEqual([(g["rule"], g["bounce_to"]) for g in out["gaps"]], [("adr.checks", "architect")])
        self.put("checks/port-exists.sh", "#!/bin/sh\n", base=self.repo)
        self.run_tool("lint", self.feat, expect=0)

    def test_adr_check_from_resolved_project_wide(self):
        old = os.path.join(self.out, "features", "old")
        self.put("building-blocks.yaml", "blocks:\n  - id: old-agg\n    type: aggregate\n  - id: old-rm\n"
                 "    type: read-model\n", base=old)
        self.put("integrated/old-agg.json", '{"id": "old-agg"}', base=old)
        self.put("decisions/0001-money.md", "---\nenforced_by:\n  - { check: checks/a.sh, from: old-agg }\n"
                 "  - { check: checks/b.sh, from: old-rm }\n  - { check: checks/c.sh, from: ghost }\n---\n"
                 "# 0001\n\n## Decision\ncents\n", base=self.out)
        self.put("checks/c.sh", "#!/bin/sh\n", base=self.repo)
        md = self.run_tool("pack", self.feat, "agg-order", expect=0)
        self.assertIn("`checks/a.sh` — applicable (from old-agg)", md)   # integrated by a previous feature
        self.assertIn("`checks/b.sh` — not yet applicable", md)
        self.assertIn("`checks/c.sh` — UNRESOLVED", md)
        gaps, out = self.gaps()
        texts = [g["gap"] for g in out["gaps"] if g["rule"] == "adr.checks"]
        self.assertEqual(len(texts), 2, texts)
        self.assertTrue(any("checks/a.sh not found" in t for t in texts))    # applicable → must exist
        self.assertTrue(any("from ghost" in t for t in texts))               # unresolvable even if it exists
        self.assertIn(("checks/b.sh", "old-rm is integrated"), [(d["file"], d["until"]) for d in out["deferred"]])

    def test_block_named_as_from_gets_the_adr_in_its_pack(self):
        self.put("decisions/0002-ports.md", "---\nenforced_by:\n  - { check: checks/port.sh, from: svc-report }\n"
                 "---\n# 0002 — Ports\n\n## Decision\nports\n", base=self.out)  # in no related_adrs
        h = self.spec_hash("svc-report")
        self.assertIn("`checks/port.sh` — applicable: THIS block writes it",
                      self.run_tool("pack", self.feat, "svc-report", expect=0))
        self.put("decisions/0002-ports.md", "---\nenforced_by:\n  - { check: checks/port.sh, from: svc-report }\n"
                 "---\n# 0002 — Ports\n\n## Decision\nports v2\n", base=self.out)
        self.assertNotEqual(h, self.spec_hash("svc-report"))

    def test_legacy_enforced_by_is_a_gap_never_run(self):
        self.put("decisions/0001-money.md", "---\nenforced_by: \"! grep -rn 'float' src/\"\n---\n# 0001\n",
                 base=self.out)
        gaps, out = self.gaps()
        self.assertIn(("adr.checks", "decisions/0001-money.md"), gaps)
        self.assertIn("grep -rn", out["gaps"][0]["gap"])

    def test_unparseable_manifest_exits_2_with_line(self):
        self.write_feature(MANIFEST + "bad: [INV-1] unquoted\n")
        out = self.run_tool("lint", self.feat, expect=2)
        self.assertIn("line %d" % (MANIFEST.count("\n") + 1), out["error"])


class TestFlow(Base):
    def test_log56_diff_range_from_merge_base(self):
        wt = self.block_wt("rm-orders")
        self.commit(wt, "src/orders.txt", "mine\n")
        self.line_commit("src/other_block.txt", "someone else's\n")  # lands on the line after branching
        out = self.run_tool("diff-range", "--base", "feature/shop", "--head", "block/rm-orders", expect=0, cwd=wt)
        self.assertEqual(out["files"], [{"status": "A", "path": "src/orders.txt"}])
        self.assertEqual(out["head_sha"], sh(wt, "git", "rev-parse", "HEAD"))
        self.assertIn("D\tsrc/other_block.txt", sh(self.repo, "git", "diff", "--name-status", "feature/shop", "block/rm-orders"))

    def test_move_illegal_and_done_only_when_finishable(self):
        out = self.run_tool("move", self.feat, "agg-order", "--to", "done", expect=1)
        self.assertIn("illegal", out["refused"])
        out = self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=0)
        self.assertTrue(out["git"])
        self.assertIn("R  .mismagent/features/shop/blocks/orders/todo/agg-order.md -> "
                      ".mismagent/features/shop/blocks/orders/doing/agg-order.md", sh(self.repo, "git", "status", "--porcelain"))
        self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=1)
        self.integrate("agg-order")
        self.assertIn("not finishable", self.run_tool("move", self.feat, "agg-order", "--to", "done", expect=1)["refused"])
        for bid in ("svc-order", "rm-orders"):   # b-order welded once owner + every consumer are in
            self.integrate(bid)
        self.assertEqual(self.run_tool("ready", self.feat, expect=0)["finishable"], ["agg-order"])
        self.run_tool("move", self.feat, "agg-order", "--to", "done", expect=0)

    def test_move_spike_node(self):
        self.put("tasks/be/backlog/perf-spike.md", "---\nid: perf-spike\ntype: spike\n---\n")
        self.run_tool("move", self.feat, "perf-spike", "--to", "done", expect=1)
        self.assertEqual(self.run_tool("move", self.feat, "perf-spike", "--to", "doing", expect=0)["git"], False)
        self.run_tool("move", self.feat, "perf-spike", "--to", "done", expect=0)

    def ready_ids(self):
        return [r["id"] for r in self.run_tool("ready", self.feat, expect=0)["ready"]]

    def test_ready_owner_integrated_parked_spike_order(self):
        self.assertEqual(self.ready_ids(), ["scaffold-app"])          # the scaffold goes alone, first
        self.integrate("scaffold-app")
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=1)  # todo -> done is illegal
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        self.assertEqual(self.ready_ids(), ["agg-order"])
        self.move("agg-order", "doing")
        self.block_wt("agg-order")                    # a branch alone is not integration
        self.assertNotIn("svc-order", self.ready_ids())
        self.commit(os.path.join(self.tmp, "wt", "agg-order"), "src/a.txt", "a\n")
        self.review("agg-order")
        self.compose("start", "agg-order", expect=0)
        self.compose("promote", "agg-order", expect=0)
        self.assertEqual(self.ready_ids(), ["svc-order", "rm-orders"])  # wave, then release
        self.put("open-questions/svc-order.md", "which currency?\n")
        out = self.run_tool("ready", self.feat, expect=0)
        self.assertIn("parked", {e["id"]: e["reason"] for e in out["excluded"]}["svc-order"])
        self.put("tasks/be/backlog/perf-spike.md", "---\nid: perf-spike\ntype: spike\ncentral: true\n---\n"
                 "# Spike\n\n## Unblocks\n- rm-orders\n")
        out = self.run_tool("ready", self.feat, expect=0)
        self.assertEqual([r["id"] for r in out["ready"]], [])
        self.assertEqual(out["open_spikes"], [{"id": "perf-spike", "state": "backlog", "central": True, "unblocks": ["rm-orders"]}])

    def test_ready_scaffold_barrier(self):
        self.put("tasks/be/backlog/perf-spike.md", "---\nid: perf-spike\ntype: spike\n---\n# S\n\n## Unblocks\n- rm-orders\n")
        out = self.run_tool("ready", self.feat, expect=0)
        self.assertEqual([r["id"] for r in out["ready"]], ["scaffold-app"])
        self.assertIn("scaffold not integrated and done: scaffold-app", {e["id"]: e["reason"] for e in out["excluded"]}["agg-order"])
        self.assertEqual([s["id"] for s in out["open_spikes"]], ["perf-spike"])       # spikes stay visible
        self.move("scaffold-app", "doing")
        self.assertEqual(self.ready_ids(), [])                                        # doing: still the barrier
        self.integrate("scaffold-app")
        self.assertEqual(self.ready_ids(), [])                                        # integrated, not done
        self.assertEqual(self.run_tool("ready", self.feat, expect=0)["finishable"], ["scaffold-app"])
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        self.assertEqual(self.ready_ids(), ["agg-order"])

    def test_ready_two_scaffolds_and_brownfield(self):
        two = MANIFEST.replace("blocks:\n", "blocks:\n  - id: scaffold-ui\n    type: scaffold\n    context: shell\n    wave: 0\n", 1)
        self.write_feature(two)
        self.put("blocks/shell/todo/scaffold-ui.md", block_file("scaffold-ui", "scaffold", "shell", 0))
        self.assertEqual(self.ready_ids(), ["scaffold-ui", "scaffold-app"])
        self.integrate("scaffold-app")
        self.move("scaffold-app", "done")
        self.assertEqual(self.ready_ids(), ["scaffold-ui"])                          # every scaffold first
        brown = MANIFEST.replace("  - id: scaffold-app\n    type: scaffold\n    context: shell\n    wave: 0\n", "")
        self.write_feature(brown, skip=("scaffold-app",))
        self.assertEqual(self.ready_ids(), ["agg-order"])                             # no scaffold: no barrier

    def snapshot(self):
        return sorted(os.path.relpath(p, self.feat) for p in glob.glob(os.path.join(self.feat, "**"), recursive=True))

    def test_move_refusal_is_unmistakable(self):
        before = self.snapshot()
        for bid, to in (("agg-order", "done"), ("scaffold-app", "todo")):
            out = self.run_tool("move", self.feat, bid, "--to", to, expect=1)
            self.assertEqual((out["ok"], "to" in out, out["from"]), (False, False, "todo"))
            self.assertIn("refused", out)
        self.move("agg-order", "doing")
        before = self.snapshot()
        out = self.run_tool("move", self.feat, "agg-order", "--to", "done", expect=1)
        self.assertEqual((out["ok"], "to" in out), (False, False))
        self.assertIn("not finishable", out["refused"])
        self.assertEqual(self.snapshot(), before)                                     # nothing moved
        out = self.run_tool("move", self.feat, "agg-order", "--to", "todo", expect=0)
        self.assertEqual((out["ok"], out["to"]), (True, "todo"))

    # -- compose
    def started(self, bid="rm-orders"):
        wt = self.block_wt(bid)
        self.commit(wt, "src/rm.txt", "rm\n")
        self.review(bid)
        return self.compose("start", bid, expect=0)

    def test_compose_green_path(self):
        base = sh(self.repo, "git", "rev-parse", "feature/shop")
        out = self.started()
        self.assertEqual(out["base_sha"], base)
        self.assertEqual(sh(self.repo, "git", "rev-parse", "feature/shop"), base)       # line untouched
        self.compose("start", "svc-order", expect=1)                                    # one at a time
        self.assertTrue(self.compose("promote", "rm-orders", expect=0)["promoted"])
        rec = json.load(open(os.path.join(self.feat, "integrated", "rm-orders.json")))
        self.assertEqual((rec["sha"], rec["merge"]), (out["branch_sha"], out["candidate_sha"]))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "feature/shop"), out["candidate_sha"])
        self.assertFalse(os.path.exists(out["candidate_path"]))

    def test_start_refused_without_fresh_review(self):
        wt = self.block_wt("rm-orders")
        self.commit(wt, "src/rm.txt", "rm\n")
        self.assertIn("no fresh review", self.compose("start", "rm-orders", expect=1)["refused"])
        self.review("rm-orders")
        self.commit(wt, "src/rm.txt", "rm2\n")                                           # reviewed sha != HEAD
        self.compose("start", "rm-orders", expect=1)

    def test_promote_refused_dirty_candidate(self):
        out = self.started()
        self.put("wip.txt", "x\n", base=out["candidate_path"])
        self.assertIn("uncommitted", " ".join(self.compose("promote", "rm-orders", expect=1)["refused"]))

    def test_promote_refused_head_moved(self):
        out = self.started()
        self.commit(out["candidate_path"], "fix.txt", "x\n")
        self.assertIn("recorded merge", " ".join(self.compose("promote", "rm-orders", expect=1)["refused"]))

    def test_promote_refused_line_moved(self):
        self.started()
        moved = self.line_commit("src/other.txt", "x\n")
        self.assertIn("moved", " ".join(self.compose("promote", "rm-orders", expect=1)["refused"]))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "feature/shop"), moved)

    def test_promote_refused_stale_review_after_spec_change(self):
        self.started()
        with open(os.path.join(self.feat, "blocks/orders/todo/rm-orders.md"), "a") as f:
            f.write("- a criterion added after the PASS\n")
        out = self.compose("promote", "rm-orders", expect=1)
        self.assertIn("the spec changed after the review", out["refused"])
        self.assertFalse(os.path.exists(os.path.join(self.feat, "integrated", "rm-orders.json")))

    def test_promote_on_checked_out_line(self):
        sh(self.repo, "git", "checkout", "-q", "feature/shop")
        out = self.started()
        self.compose("promote", "rm-orders", expect=0)
        self.assertEqual(sh(self.repo, "git", "rev-parse", "HEAD"), out["candidate_sha"])
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "src/rm.txt")))

    def test_abort_keeps_branch_and_works_half_created(self):
        out = self.started()
        self.assertEqual(self.compose("abort", "rm-orders", expect=0)["kept_branch"], "candidate/rm-orders")
        self.assertEqual(sh(self.repo, "git", "rev-parse", "candidate/rm-orders"), out["candidate_sha"])
        self.assertFalse(os.path.exists(out["candidate_path"]))
        # half-created: metadata "starting" + a worktree, no merge (a crash mid-start)
        mdir = os.path.join(self.repo, ".git", "mismagent-candidates")
        self.put("svc-order.json", json.dumps({"id": "svc-order", "state": "starting"}), base=mdir)
        sh(self.repo, "git", "worktree", "add", "-q", "-B", "candidate/svc-order", os.path.join(mdir, "svc-order"), "feature/shop")
        self.assertIn("half-created", self.compose("promote", "svc-order", expect=1)["refused"])
        self.assertEqual(self.run_tool("status", self.feat, "--integration", "feature/shop", expect=1)["anomalies"][0]["kind"],
                         "leftover_candidate")
        self.compose("abort", "svc-order", expect=0)
        self.assertEqual(os.listdir(mdir), [])
        self.run_tool("status", self.feat, "--integration", "feature/shop", expect=0)

    def test_status_anomalies(self):
        self.run_tool("status", self.feat, "--integration", "feature/shop", expect=0)
        self.move("svc-order", "doing")                                          # doing, no worktree
        self.started()                                                           # leftover candidate
        self.review("agg-order", "feature/shop")
        self.put("blocks/orders/todo/agg-order.md", "changed\n")                 # stale review proof
        self.commit(self.repo, "main-only.txt", "x\n")
        self.put("integrated/svc-report.json", json.dumps({"sha": sh(self.repo, "git", "rev-parse", "main")}))
        self.move("scaffold-app", "done")                                        # done, not integrated
        out = self.run_tool("status", self.feat, "--integration", "feature/shop", expect=1)
        self.assertEqual({(x["kind"], x["id"]) for x in out["anomalies"]},
                         {("doing_without_worktree", "svc-order"), ("leftover_candidate", "rm-orders"),
                          ("stale_review_proof", "agg-order"), ("integrated_not_on_line", "svc-report"),
                          ("done_unwelded", "scaffold-app")})

    def test_status_worktree_directory_deleted(self):
        self.move("svc-order", "doing")
        shutil.rmtree(self.block_wt("svc-order"))              # deleted without `git worktree remove`
        out = self.run_tool("status", self.feat, "--integration", "feature/shop", expect=1)
        self.assertEqual({(x["kind"], x["id"]) for x in out["anomalies"]},
                         {("doing_without_worktree", "svc-order"), ("missing_worktree", "block/svc-order")})

    # -- proofs
    def gate(self, op, *extra, feat=None, expect=None):
        return self.run_tool("proof", op, feat or self.feat, "gate", "be", *extra, expect=expect)

    def test_gate_record_warns_on_generated_matches_and_still_hashes_them(self):
        self.put(".gitignore", "*.log\n", base=self.repo)
        self.put("src/app.cfg", "a\n", base=self.repo)
        self.put("build/gen.cfg", "g1\n", base=self.repo)
        self.put("src/run.log", "x\n", base=self.repo)
        out = self.gate("record", "--gate", "make test", "--gate-files", "src/*.cfg", expect=0)
        self.assertNotIn("warnings", out)
        out = self.gate("record", "--gate", "make test", "--gate-files", "**/*.cfg", "src/*.log", expect=0)
        self.assertEqual(out["warnings"]["looks_generated"], 2)
        self.assertEqual(sorted(out["warnings"]["files"]), ["build/gen.cfg: under build/", "src/run.log: git-ignored, .log file"])
        self.put("build/gen.cfg", "g2\n", base=self.repo)                        # never excluded from the hash
        self.gate("check", "--gate", "make test", "--gate-files", "**/*.cfg", "src/*.log", expect=1)

    def test_gate_proof_stale_on_gate_string_and_files(self):
        self.put("build.cfg", "strict\n", base=self.repo)
        self.gate("record", "--gate", "make test", expect=2)                               # --gate-files required
        self.gate("record", "--gate", "make test", "--gate-files", "nothing/*.cfg", expect=2)  # must match a file
        self.gate("record", "--gate", "make test", "--gate-files", "*.cfg", expect=0)
        other = os.path.join(self.out, "features", "later")
        shutil.copytree(self.feat, other, ignore=shutil.ignore_patterns("gate-proof"))
        self.assertTrue(self.gate("check", "--gate", "make test", "--gate-files", "*.cfg", feat=other, expect=0)["fresh"])
        out = self.gate("check", "--gate", "make test-all", "--gate-files", "*.cfg", expect=1)
        self.assertIn("gate string changed", out["stale_because"])
        self.put("build.cfg", "lenient\n", base=self.repo)
        out = self.gate("check", "--gate", "make test", "--gate-files", "*.cfg", expect=1)
        self.assertIn("gate files changed (list or content)", out["stale_because"])

    def test_review_proof_record_check(self):
        wt = self.block_wt("svc-order")
        s = self.commit(wt, "src/s.txt", "s\n")
        self.review("svc-order")
        self.assertTrue(self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", s, expect=0)["fresh"])
        self.put("decisions/0001-money.md", "# 0001\n\n## Decision\ncents\n", base=self.out)  # the owner's ADR
        out = self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", s, expect=1)
        self.assertEqual(out["stale_because"], ["the spec changed after the review"])

    def test_review_record_refuses_a_spec_the_reviewers_did_not_see(self):
        self.block_wt("svc-order")
        seen = self.spec_hash("svc-order")                                   # the pack the reviewers got
        with open(os.path.join(self.feat, "blocks/orders/todo/svc-order.md"), "a") as f:
            f.write("- a criterion added during the review\n")
        out = self.review("svc-order", h=seen, expect=1)
        self.assertIn("spec changed", out["refused"])
        self.assertFalse(os.path.exists(os.path.join(self.feat, "review-proof", "svc-order.json")))
        self.run_tool("proof", "record", self.feat, "review", "svc-order", "--sha", "block/svc-order", expect=2)

    def test_pre_release_group_packs_and_proves_its_rework_files(self):
        self.run_tool("pack", self.feat, "pre-R0-1", expect=2)                  # no rework file yet
        self.put("rework/pre-R0-1-1.md", "- [ ] R0 · svc-order · MED · a.py:1 · naming\n")
        self.assertIn("naming", self.run_tool("pack", self.feat, "pre-R0-1", expect=0))
        self.block_wt("pre-R0-1")
        seen = self.spec_hash("pre-R0-1")
        self.put("rework/pre-R0-1-1.md", "- [ ] R0 · svc-order · MED · a.py:1 · naming, and more\n")
        self.review("pre-R0-1", h=seen, expect=1)
        self.review("pre-R0-1")


class TestPack(Base):
    def test_pack(self):
        self.put("product-brief.md", "# Brief\nSell things.\n")
        self.put("decisions/0001-money.md", "# 0001 — Money as cents\n\n## Context\nskip me\n\n"
                 "## Decision\nUse integer cents.\n\n## Consequences\nno floats\n", base=self.out)
        self.put("architetture/lessons-by-block-type.md", "# Lessons\n\n## application-service\n- check the wiring\n"
                 "- ~~always retry~~ struck\n  continuation of struck\n\n## aggregate\n- agg lesson\n", base=self.out)
        extra = self.put("dev-arch.md", "style memory\n", base=self.tmp)
        md = self.run_tool("pack", self.feat, "svc-order", "--extra", extra, expect=0)
        for s in ("source: `.mismagent/features/shop/product-brief.md`", "## Boundary b-order", "Use integer cents.",
                  "no floats", "check the wiring", "style memory"):
            self.assertIn(s, md)
        for s in ("skip me", "always retry", "continuation of struck", "agg lesson"):
            self.assertNotIn(s, md)

    def test_pack_carries_enforced_by_checks_with_applicability(self):
        self.put("decisions/0001-money.md", "---\nstatus: accepted\nenforced_by:\n  - check: checks/no-float.sh\n"
                 "  - check: checks/port-exists.sh\n    from: svc-order\n  - \"grep -rn legacy src/\"\n---\n"
                 "# 0001 — Money\n\n## Decision\ncents\n", base=self.out)
        own = self.run_tool("pack", self.feat, "svc-order", expect=0)
        self.assertIn("`checks/no-float.sh` — applicable", own)
        self.assertIn("`checks/port-exists.sh` — applicable: THIS block writes it", own)
        self.assertIn("LEGACY `grep -rn legacy src/`", own)
        other = self.run_tool("pack", self.feat, "rm-orders", expect=0)
        self.assertIn("`checks/port-exists.sh` — not yet applicable: from svc-order", other)
        self.put("integrated/svc-order.json", '{"id": "svc-order"}')
        self.assertIn("`checks/port-exists.sh` — applicable (from svc-order)",
                      self.run_tool("pack", self.feat, "rm-orders", expect=0))
        scaffold = self.run_tool("pack", self.feat, "scaffold-app", expect=0)  # it writes the no-`from` checks
        self.assertIn("`checks/no-float.sh` — applicable", scaffold)

    def test_consumer_pack_carries_the_owners_adr_guarantees_and_a_change_stales_its_review(self):
        adr = "# 0001 — Order events\n\n## Context\nskip me\n\n## Decision\nOrderPlaced: %s, may repeat.\n"
        self.put("decisions/0001-orders.md", adr % "at-least-once, unordered", base=self.out)
        self.assertIn("at-least-once, unordered", self.run_tool("pack", self.feat, "rm-orders", expect=0))
        s = self.commit(self.block_wt("rm-orders"), "src/rm.txt", "rm\n")
        self.review("rm-orders")
        self.assertTrue(self.run_tool("proof", "check", self.feat, "review", "rm-orders", "--sha", s, expect=0)["fresh"])
        self.put("decisions/0001-orders.md", adr % "at-least-once, ordered per orderId", base=self.out)
        out = self.run_tool("proof", "check", self.feat, "review", "rm-orders", "--sha", s, expect=1)
        self.assertEqual(out["stale_because"], ["the spec changed after the review"])

    def test_lesson_written_as_harvest_prescribes_reaches_the_pack(self):
        with open(os.path.join(PLUGIN, "skills", "harvest-dev-architecture", "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        m = re.search(r"under \*\*`(#+) <type>`\*\*", skill)
        self.assertIsNotNone(m, "harvest must prescribe the lessons heading as under **`## <type>`**")
        self.put("architetture/lessons-by-block-type.md", "# Lessons by block type\n\n%s application-service\n"
                 "- application-service: go through the root — see `src/x.txt`\n" % m.group(1), base=self.out)
        self.assertIn("go through the root", self.run_tool("pack", self.feat, "svc-order", expect=0))


RENDERED = """\
blocks:
  - id: scaffold-app
    type: scaffold
    context: shell
    wave: 0
  - id: agg-order
    type: aggregate
    context: orders
    wave: 1
    release: R0
    what: "The Order aggregate: places orders and guards their totals."
    sources: [tactical-model#orders, ADR 0001]
    related_adrs: ["0001"]
    invariants:
      - "[INV-1] an order total is never negative"
    tests_nl: ["INV-1 a negative total is rejected"]
  - id: svc-order
    type: application-service
    context: orders
    wave: 2
    release: R0
    what: "PlaceOrder: validates the lines, asks the aggregate, returns the id."
    sources: [tactical-model#orders]
    consumes: [b-order]
    commands: [PlaceOrder]
    tests_nl: ["PlaceOrder creates an order", "PlaceOrder with no lines is rejected"]
boundaries:
  - id: b-order
    owner: agg-order
    consumers: [svc-order]
    pinned_types: { OrderPlaced: "orderId:string · total:int" }
    keys: { orderId: "minted by agg-order — uuid4, stable" }
    contract_test: invariant-test
releases:
  R0: { goal: "place an order", launch: "orders screen", blocks: [agg-order, svc-order] }
"""


class TestRender(Base):
    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.feat, "blocks"))
        self.put("building-blocks.yaml", RENDERED)

    def render(self, expect=0):
        return self.run_tool("manifest", "render", self.feat, expect=expect)

    def files(self):
        out = {}
        for p in sorted(glob.glob(os.path.join(self.feat, "blocks", "*", "*", "*.md"))):
            with open(p) as f:
                out[os.path.relpath(p, self.feat)] = f.read()
        return out

    def test_render_is_deterministic_lint_green_and_idempotent(self):
        out = self.render()
        self.assertEqual(sorted(out["written"]), ["blocks/orders/todo/agg-order.md", "blocks/orders/todo/svc-order.md",
                                                  "blocks/shell/todo/scaffold-app.md"])
        first = self.files()
        svc = first["blocks/orders/todo/svc-order.md"]
        for want in ("## What to do\nPlaceOrder: validates", "- PlaceOrder with no lines is rejected",
                     "`b-order` (consumes it; owner `agg-order`)", "pinned `OrderPlaced`: orderId:string · total:int",
                     "key `orderId`: minted by agg-order", "Sources: tactical-model#orders"):
            self.assertIn(want, svc)
        self.assertIn("## Invariants\n- [INV-1] an order total is never negative", first["blocks/orders/todo/agg-order.md"])
        self.run_tool("lint", self.feat, expect=0)
        out = self.render()
        self.assertEqual((out["written"], len(out["unchanged"])), ([], 3))
        self.assertEqual(self.files(), first)

    def test_boundary_change_propagates_in_place_and_stales_the_spec(self):
        self.render()
        self.move("svc-order", "doing")
        self.move("agg-order", "done")
        before = self.spec_hash("svc-order")
        self.put("building-blocks.yaml", RENDERED.replace("total:int\" }", "total:int · currency:string\" }"))
        out = self.render()
        self.assertEqual(sorted(out["written"]), ["blocks/orders/doing/svc-order.md", "blocks/orders/done/agg-order.md"])
        self.assertEqual(sorted(self.files()), ["blocks/orders/doing/svc-order.md", "blocks/orders/done/agg-order.md",
                                                "blocks/shell/todo/scaffold-app.md"])  # nothing moved
        self.assertIn("currency:string", self.files()["blocks/orders/doing/svc-order.md"])
        self.assertNotEqual(self.spec_hash("svc-order"), before)
        with open(os.path.join(self.feat, "blocks/orders/doing/svc-order.md"), "a") as f:
            f.write("- a hand-patched criterion\n")
        self.assertIn(("blockfile.render", "svc-order"), self.gaps()[0])

    def test_incomplete_or_conflicting_input_writes_nothing(self):
        self.render()
        before = self.files()
        bad = RENDERED.replace('    what: "PlaceOrder: validates the lines, asks the aggregate, returns the id."\n', "")
        bad = bad.replace('tests_nl: ["INV-1 a negative total is rejected"]', 'tests_nl: ["a total is checked"]')
        bad = bad.replace("The Order aggregate", "The ORDER aggregate")        # a change that would be written
        self.put("building-blocks.yaml", bad)
        out = self.render(expect=1)
        self.assertFalse(out["ok"])
        self.assertEqual(sorted(p["id"] for p in out["problems"]), ["agg-order", "svc-order"])
        self.assertEqual(self.files(), before)
        self.put("building-blocks.yaml", RENDERED.replace("context: orders\n    wave: 2", "context: sales\n    wave: 2"))
        self.assertIn("context change", self.render(expect=1)["problems"][0]["problem"])
        dup = RENDERED[RENDERED.index("  - id: svc-order"):RENDERED.index("boundaries:")]
        self.put("building-blocks.yaml", RENDERED.replace("boundaries:", dup + "boundaries:", 1))
        self.assertIn("duplicate block id", str(self.render(expect=1)["problems"]))
        self.assertEqual(self.files(), before)

    def test_blank_criteria_and_sources_are_missing_before_any_write(self):
        before = self.files()
        for bad in (RENDERED.replace('"PlaceOrder with no lines is rejected"', '""'),
                    RENDERED.replace("sources: [tactical-model#orders]\n", 'sources: "   "\n'),
                    RENDERED.replace("sources: [tactical-model#orders]\n", 'sources: [" "]\n')):
            self.put("building-blocks.yaml", bad)
            out = self.render(expect=1)
            self.assertEqual({p["id"] for p in out["problems"]}, {"svc-order"}, out)
            self.assertEqual(self.files(), before)                              # nothing written
        self.put("building-blocks.yaml", RENDERED)
        self.render()
        self.put("building-blocks.yaml", RENDERED.replace("sources: [tactical-model#orders]\n", 'sources: "   "\n'))
        self.assertIn(("render.input", "svc-order"), self.gaps()[0])            # lint: the same validation

    def test_malformed_pins_and_keys_are_refused_never_dropped(self):
        before = self.files()
        for bad in (RENDERED.replace('pinned_types: { OrderPlaced: "orderId:string · total:int" }',
                                     'pinned_types: ["OrderPlaced: orderId:string"]'),
                    RENDERED.replace('keys: { orderId: "minted by agg-order — uuid4, stable" }', 'keys: "orderId"')):
            self.put("building-blocks.yaml", bad)
            out = self.render(expect=1)
            self.assertIn("is not a mapping", str(out["problems"]))
            self.assertEqual(self.files(), before)
            self.assertIn(("boundary.pinned_types", "b-order"), self.gaps()[0])


def note(i, scope="feature", status="accepted", drop=(), **over):
    f = {"Meta": "2026-09-24; scope: %s; status: %s" % (scope, status), "Question": "Which parser?",
         "Options": "A split, fails on quotes; B standard parser.", "Hypothesis": "B reads every agreed format.",
         "Check": "Run the 24 agreed fixtures; success = 24 matches.", "Result": "B 24/24; [run](https://ci.example.com/412).",
         "Debate": "none", "Decision": "B %s; we accept one dialect." % i,
         "By": "decided: mismagent-worker/agg-order (deep); recorded: worker-composer",
         "Docs": "[spec](https://example.com/rfc4180)", "Revisit": "revisit-%s" % i}
    f.update(over)
    return "### %s · Parser choice\n%s\n" % (i, "".join("- %s: %s\n" % kv for kv in f.items() if kv[0] not in drop))


class TestWhy(Base):
    def why(self, text, expect):
        path = self.put("decisions.md", "# Decision notes — shop\n\n" + text)
        return self.run_tool("why", "check", path, expect=expect)

    def rules(self, text):
        return {(e["id"], e["rule"]) for e in self.why(text, 1)["errors"]}

    def test_a_handoff_imports_with_local_ids_idempotently(self):
        d = os.path.join(self.tmp, "imp")
        path = self.put("decisions.md", note("D-0001") + "\n" + note("D-0002"), base=d)
        h = self.put("h.md", note("D-0001", Decision="first local") + "\n" +
                     note("D-0002", Decision="second local", Debate="builds on D-0001; unlike D-0002 above") +
                     "\nRESULT: READY-FOR-REVIEW\nBLOCK: agg-order\n", base=d)
        out = self.run_tool("why", "check", h, "--into", path, expect=0)                 # dry: nothing written
        self.assertEqual(out["mapping"], {"D-0001": "D-0003", "D-0002": "D-0004"})
        self.assertNotIn("D-0003", mismagent.read(path))
        out = self.run_tool("why", "import", path, "--handoff", h, expect=0)
        self.assertEqual((out["appended"], out["unchanged"]), (["D-0003", "D-0004"], []))
        text = mismagent.read(path)
        self.assertIn("- Debate: builds on D-0003; unlike D-0004 above", text)           # local refs remapped
        self.assertNotIn("RESULT:", text)
        out = self.run_tool("why", "import", path, "--handoff", h, expect=0)             # a retry adds nothing
        self.assertEqual((out["appended"], out["unchanged"]), ([], ["D-0003", "D-0004"]))
        self.assertEqual(mismagent.read(path), text)
        bad = self.put("bad.md", note("D-0001", Docs="[x](missing.md)"), base=d)
        out = self.run_tool("why", "check", bad, "--into", path, expect=1)
        self.assertIn("link.missing", {e["rule"] for e in out["errors"]})
        self.assertEqual(mismagent.read(path), text)

    def test_a_handoff_import_survives_cycles_updates_and_rejects_malformed_notes(self):
        d = os.path.join(self.tmp, "imp2")
        path = self.put("decisions.md", note("D-0001"), base=d)
        h = self.put("x-1.md", note("D-0001", Debate="see D-0002") + "\n" + note("D-0002", Debate="see D-0001"), base=d)
        out = self.run_tool("why", "import", path, "--handoff", h, expect=0)
        self.assertEqual((out["mapping"], out["appended"]), ({"D-0001": "D-0002", "D-0002": "D-0003"}, ["D-0002", "D-0003"]))
        text = mismagent.read(path)
        self.assertIn("- Debate: see D-0003", text)                                       # mapped once, never twice
        self.assertEqual(self.run_tool("why", "import", path, "--handoff", h, expect=0)["appended"], [])  # cycle: no-op
        self.put("x-1.md", note("D-0001", Debate="see D-0002; the reviewer agreed") + "\n" +
                 note("D-0002", Debate="see D-0001"), base=d)
        out = self.run_tool("why", "import", path, "--handoff", h, expect=0)              # an allowed update
        self.assertEqual((out["appended"], out["updated"]), ([], ["D-0002"]))
        self.assertEqual(len(mismagent.parse_notes(path)[0]), 3)
        for bad in ("## D-0001 · Parser choice\n", note("D-0001").replace("- Question: Which parser?\n",
                                                                           "- Question: Which\n  parser?\n")):
            self.put("y-1.md", bad, base=d)
            out = self.run_tool("why", "check", os.path.join(d, "y-1.md"), "--into", path, expect=1)
            self.assertEqual(out["errors"][0]["rule"], "handoff.line")

    def test_valid_file_before_any_manifest(self):
        d = os.path.join(self.tmp, "early")
        path = self.put("decisions.md", note("D-0001") + note("D-0002", Supersedes="D-0001"), base=d)
        with open(path) as f:
            text = f.read().replace("status: accepted", "status: superseded", 1)
        with open(path, "w") as f:
            f.write(text)
        out = self.run_tool("why", "check", path, expect=0)
        self.assertEqual((out["entries"], out["active"]), (2, 1))
        self.assertIn("error", self.run_tool("why", "check", os.path.join(d, "none.md"), expect=2))

    def test_invalid_entries(self):
        long = " ".join(["word"] * 26)
        got = self.rules(note("D-0001", drop=("Debate",)) + note("D-0002", Question=long) + note("D-0002")
                         + note("D-0003", **{k: " ".join(["w"] * n) for k, n in mismagent.NOTE_FIELDS.items()
                                             if n and k != "Confidence"})  # each at its cap, the sum over 220
                         + note("D-0004", Result="untested") + note("D-0005", Docs="none", By="the composer")
                         + note("D-0006", Supersedes="D-0009") + note("D-0007", status="superseded")
                         + note("D-0008", Docs="[x](missing/file.md)", Meta="24/09/2026; scope: team"))
        for want in [("D-0001", "field.missing"), ("D-0002", "field.cap"), ("D-0002", "id.duplicate"),
                     ("D-0003", "entry.cap"), ("D-0004", "result.reason"), ("D-0005", "docs.links"),
                     ("D-0005", "by.roles"), ("D-0006", "supersede.target"), ("D-0007", "supersede.link"),
                     ("D-0008", "link.missing"), ("D-0008", "meta.date"), ("D-0008", "meta.scope"),
                     ("D-0008", "meta.status")]:
            self.assertIn(want, got)
        self.assertNotIn(("D-0003", "field.cap"), got)
        self.assertIn(("D-0001", "supersede.status"), self.rules(note("D-0001") + note("D-0002", Supersedes="D-0001")))
        self.assertIn(("-", "id.order"), self.rules(note("D-0002") + note("D-0001")))

    def test_lax_fields_and_malformed_headings_are_errors(self):
        got = self.rules(note("D-0001", Result="B 24/24, all green.") + note("D-0002", By="decided: ; recorded: composer")
                         + note("D-0003", Confidence="high") + note("D-0004", ADR="none"))
        for want in [("D-0001", "result.link"), ("D-0002", "by.roles"), ("D-0003", "confidence.level"),
                     ("D-0004", "adr.link")]:
            self.assertIn(want, got)
        for bad in ("  " + note("D-0001"), note("D-0001").replace("### ", "## ", 1)):
            out = self.why(bad, 1)
            self.assertTrue(any(e["rule"] == "entry.header" for e in out["errors"]), out)

    def test_post_close_edits_status_and_adr_backlink_stay_valid(self):
        self.put("adr.md", "# ADR\n")
        self.why(note("D-0001", status="superseded", ADR="[ADR 0003](adr.md)", Confidence="high — measured")
                 + note("D-0002", Supersedes="D-0001", Result="untested — no corpus yet"), 0)

    def test_lint_runs_the_validator_and_checks_scopes(self):
        self.assertTrue(self.gaps()[1]["ok"])  # no decisions.md: nothing to check
        self.put("decisions.md", note("D-0001", drop=("Revisit",)) + note("D-0002", scope="block:nope"))
        gaps = self.gaps()[0]
        self.assertIn(("why.field.missing", "decisions.md D-0001"), gaps)
        self.assertIn(("why.scope", "decisions.md D-0002"), gaps)

    def test_pack_selects_active_notes_and_spec_hash_ignores_them(self):
        before = self.spec_hash("svc-order")
        self.put("decisions.md", note("D-0001", scope="block:agg-order", status="superseded")
                 + note("D-0002", scope="block:agg-order", Supersedes="D-0001") + note("D-0003", scope="block:svc-report")
                 + note("D-0004", scope="boundary:b-order") + note("D-0005") + note("D-0006", scope="boundary:b-rm")
                 + note("D-0007", scope="block:svc-order"))
        md = self.run_tool("pack", self.feat, "svc-order", expect=0)
        for i in ("D-0002", "D-0004", "D-0005", "D-0007"):  # owner, touched boundary, feature, itself
            self.assertIn("revisit-" + i, md)
        for i in ("D-0001", "D-0003", "D-0006"):  # superseded, unrelated block, untouched boundary
            self.assertNotIn("revisit-" + i, md)
        self.assertIn("(decisions.md#d-0007--parser-choice)", md)  # the GitHub anchor of the full heading
        self.assertEqual(self.spec_hash("svc-order"), before)


class TestNotesShortFormAndAppend(Base):
    SHORT = {"Hypothesis": "n/a — decided by REQ-3", "Check": "n/a — decided by REQ-3",
             "Result": "n/a — decided by [scope cut](brief.md#out-of-scope)"}

    def rules(self, text):
        path = self.put("decisions.md", text)
        return {(e["id"], e["rule"]) for e in self.run_tool("why", "check", path)["errors"]}

    def test_short_form(self):
        self.put("brief.md", "# Brief\n")
        self.assertEqual(self.rules(note("D-0001", **self.SHORT)), set())
        got = self.rules(note("D-0001", Hypothesis="n/a — decided by REQ-3")
                         + note("D-0002", **dict(self.SHORT, Check="n/a — decided by the team"))
                         + note("D-0003", **dict(self.SHORT, Result="n/a")))
        self.assertIn(("D-0001", "short.all_three"), got)                      # never mixed with an experiment
        self.assertIn(("D-0002", "short.reference"), got)                      # the reference must be verifiable
        self.assertIn(("D-0003", "short.reference"), got)
        self.assertNotIn(("D-0002", "short.all_three"), got)

    def append(self, text, expect):
        entry = self.put("entry.md", text, base=self.tmp)
        return self.run_tool("why", "append", os.path.join(self.feat, "decisions.md"), "--entry", entry, expect=expect)

    def test_append_validates_before_writing(self):
        path = os.path.join(self.feat, "decisions.md")
        self.assertEqual(self.append(note("D-0001"), 0)["appended"], ["D-0001"])  # creates the file
        self.assertEqual(self.append(note("D-0002"), 0)["appended"], ["D-0002"])
        with open(path) as f:
            good = f.read()
        out = self.append(note("D-0002"), 0)                                    # identical: a no-op success
        self.assertEqual((out["ok"], out["appended"], out["unchanged"]), (True, [], ["D-0002"]))
        out = self.append(note("D-0002", Decision="C instead"), 1)              # same id, other content
        self.assertEqual(out["ok"], False)
        self.assertIn("already exists", out["refused"])
        out = self.append(note("D-0003", drop=("Revisit",)), 1)                 # invalid entry
        self.assertEqual(out["errors"][0]["rule"], "field.missing")
        self.append(note("D-0001", Question="x?"), 1)
        with open(path) as f:
            self.assertEqual(f.read(), good)                                    # nothing written on refusal
        self.assertFalse(os.path.exists(path + ".tmp"))
        out = self.append(note("D-0003", Supersedes="D-0001"), 0)
        self.assertEqual(out["superseded"], ["D-0001"])
        self.run_tool("why", "check", path, expect=0)
        self.run_tool("why", "append", path, expect=2)                          # --entry is required

    def test_append_updates_only_debate_result_and_adr_backlink(self):
        path = os.path.join(self.feat, "decisions.md")
        self.put("adr.md", "# ADR\n")
        self.append(note("D-0001") + note("D-0002"), 0)
        out = self.append(note("D-0001", Debate="reviewer objected on quotes; fixtures added, resolved.",
                               Result="B 24/24; [run](https://ci.example.com/413)."), 0)
        self.assertEqual((out["appended"], out["updated"]), ([], ["D-0001"]))
        adr = note("D-0001", Debate="reviewer objected on quotes; fixtures added, resolved.",
                   Result="B 24/24; [run](https://ci.example.com/413).", ADR="[ADR 0003](adr.md)")
        self.assertEqual(self.append(adr, 0)["updated"], ["D-0001"])
        with open(path) as f:
            good = f.read()
        self.assertIn("- ADR: [ADR 0003](adr.md)", good)
        self.assertLess(good.index("D-0001"), good.index("D-0002"))             # replaced in place
        self.assertIn("already exists", self.append(adr.replace("adr.md)", "other.md)"), 1)["refused"])  # backlink kept
        self.append(note("D-0002", Decision="C instead", Debate="x"), 1)       # other fields: a new entry
        self.append(note("D-0002", Debate=""), 1)                               # an update still validates
        with open(path) as f:
            self.assertEqual(f.read(), good)
        self.run_tool("why", "check", path, expect=0)


class TestAdrLint(Base):
    def test_adrs_before_any_manifest(self):
        d = os.path.join(self.tmp, "early", "decisions")
        self.put("0001-money.md", "---\nscope: global\nstatus: accepted\nenforced_by:\n  - check: checks/no-float.sh\n"
                 "  - { check: checks/port.sh, from: svc-order }\n---\n# 0001\n", base=d)
        self.put("0002-ports.md", "---\nscope: be\nstatus: proposed\nenforced_by:\n  - check: checks/no-float.sh\n---\n# 0002\n",
                 base=d)                                                         # a script shared by two ADRs
        out = self.run_tool("lint", "--adrs", d, expect=0)
        self.assertEqual(sorted(x["file"] for x in out["deferred"]), ["checks/no-float.sh", "checks/no-float.sh", "checks/port.sh"])
        self.put("0003-bad.md", "---\nstatus: maybe\nenforced_by: \"grep -rn float src/\"\n---\n# 0003\n", base=d)
        self.put("notes.md", "# no frontmatter\n", base=d)
        out = self.run_tool("lint", "--adrs", d, expect=1)
        self.assertEqual(sorted((g["rule"], g["where"]) for g in out["gaps"]),
                         [("adr.checks", "0003-bad.md"), ("adr.filename", "notes.md"), ("adr.frontmatter", "0003-bad.md"),
                          ("adr.frontmatter", "0003-bad.md"), ("adr.frontmatter", "notes.md")])
        self.assertEqual({g["bounce_to"] for g in out["gaps"]}, {"architect"})
        self.run_tool("lint", self.feat, "--adrs", d, expect=2)
        self.run_tool("lint", expect=2)


class TestBoard(Base):
    def test_integrated_block_in_doing_is_badged_and_stays_doing(self):
        import board
        self.move("agg-order", "doing")
        self.move("svc-order", "doing")
        self.put("integrated/agg-order.json", '{"id": "agg-order"}')
        got = {b["id"]: (b["status"], b["integrated"]) for b in board.scan(os.path.join(self.feat, "blocks"))}
        self.assertEqual((got["agg-order"], got["svc-order"], got["rm-orders"]),
                         (("doing", True), ("doing", False), ("todo", False)))
        self.assertIn("integrated, closing pending", board.PAGE)


class TestV022(Base):
    """v0.22: manifest mode, `Unblocks` lines, `after:`, open findings in the pack, status outcome."""

    def ready(self):
        return self.run_tool("ready", self.feat, expect=0)

    def status(self, expect=0):
        return self.run_tool("status", self.feat, "--integration", "feature/shop", expect=expect)

    def finish(self, bid):
        self.run_tool("move", self.feat, bid, "--to", "doing", expect=0)
        self.integrate(bid)
        return self.run_tool("move", self.feat, bid, "--to", "done")

    def test_legacy_manifest_is_linted_as_legacy_and_a_real_pin_change_stales_only_its_blocks(self):
        out = self.run_tool("lint", self.feat, expect=0)
        self.assertEqual(out["manifest"], "legacy")          # hand-written files: never forced to render
        self.review("agg-order", "feature/shop")
        self.review("svc-report", "feature/shop")
        self.write_feature(MANIFEST.replace("sku:string · qty:int", "sku:string · qty:int · note:string"))
        self.assertEqual(self.run_tool("lint", self.feat, expect=0)["manifest"], "legacy")
        stale = {(x["kind"], x["id"]) for x in self.status(expect=1)["anomalies"]}
        self.assertEqual(stale, {("stale_review_proof", "agg-order")})   # svc-report touches no b-order
        shutil.rmtree(os.path.join(self.feat, "blocks"))
        self.put("building-blocks.yaml", RENDERED)
        self.run_tool("manifest", "render", self.feat, expect=0)
        self.assertEqual(self.run_tool("lint", self.feat, expect=0)["manifest"], "rendered")

    def test_unblocks_reads_only_full_id_lines(self):
        self.put("tasks/be/backlog/s.md", "---\nid: s\ntype: spike\n---\n# S\n\n## Unblocks\n"
                 "Blocks derived from the R1 rows; ids are assigned by build-manifest.\n- agg-order\n"
                 "- rm-orders because it reads the view\n  - `svc-order`\n")
        self.assertEqual(self.ready()["open_spikes"][0]["unblocks"], ["agg-order"])

    def test_after_waits_for_integration_not_done(self):
        self.write_feature(MANIFEST.replace("    consumes: [b-rm]\n", "    consumes: [b-rm]\n    after: [svc-order]\n"))
        self.run_tool("lint", self.feat, expect=0)
        self.finish("scaffold-app")
        for bid in ("agg-order", "rm-orders"):
            self.finish(bid)
        excl = {e["id"]: e["reason"] for e in self.ready()["excluded"]}
        self.assertEqual(excl["svc-report"], "after, not integrated: svc-order")
        self.run_tool("move", self.feat, "svc-order", "--to", "doing", expect=0)
        self.integrate("svc-order")                   # integrated, still in doing: enough
        self.assertIn("svc-report", [r["id"] for r in self.ready()["ready"]])

    def test_after_refs_and_cycles_with_boundary_dependencies(self):
        m = (MANIFEST.replace("    related_adrs: [0001]\n", "    related_adrs: [0001]\n    after: [svc-order]\n")
             .replace("    commands: [BuildReport]\n", "    commands: [BuildReport]\n    after: [ghost, svc-report]\n"))
        self.write_feature(m + "build_order: [[scaffold-app], [agg-order]]\n")
        gaps, out = self.gaps()
        self.assertEqual(out["manifest"], "legacy")
        rules = [(g["rule"], g["where"]) for g in out["gaps"]]
        self.assertIn(("after.block", "svc-report"), rules)
        self.assertEqual(sum(1 for g in out["gaps"] if g["rule"] == "after.block"), 2)   # ghost + itself
        self.assertIn(("after.cycle", "agg-order → svc-order → agg-order"), rules)   # after + consumes
        self.assertNotIn(("manifest.build_order", "build_order"), rules)       # legacy: tolerated
        self.assertIn("manifest.build_order", [d["rule"] for d in out["deferred"]])

    def test_after_is_order_not_spec(self):
        h = self.spec_hash("svc-report")
        self.write_feature(MANIFEST.replace("    consumes: [b-rm]\n", "    consumes: [b-rm]\n    after: [svc-order]\n"))
        self.assertEqual(self.spec_hash("svc-report"), h)

    def test_pack_carries_open_findings_only(self):
        h = self.spec_hash("svc-order")
        self.put("pre-release.md", "# Pre-release\n\n- [ ] R1 · agg-order · MED · a.py:3 · share one TurnoCorrente · v · d\n"
                 "- [x] R0 · agg-order · LOW · a.py:9 · fixed naming · v · d\n"
                 "- [~] R0 · agg-order · LOW · a.py:1 · waived thing · v · d · waived: ok\n")
        md = self.run_tool("pack", self.feat, "svc-order", expect=0)
        self.assertIn("## Open findings (advisory", md)
        self.assertIn("source: `.mismagent/features/shop/pre-release.md`", md)
        self.assertIn("- line 3: R1 · agg-order · MED · a.py:3 · share one TurnoCorrente", md)
        for gone in ("fixed naming", "waived thing"):
            self.assertNotIn(gone, md)
        self.assertEqual(self.spec_hash("svc-order"), h)

    def test_status_outcome_never_a_false_done_or_idle(self):
        self.assertEqual(self.status()["outcome"], "work")                    # the scaffold is ready
        self.finish("scaffold-app")
        self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=0)
        self.block_wt("agg-order")
        out = self.status()
        self.assertEqual((self.ready()["ready"], out["outcome"]), ([], "work"))   # ready=[] is not idle
        self.run_tool("move", self.feat, "agg-order", "--to", "todo", expect=0)
        self.put("open-questions/agg-order.md", "which currency?\n")
        out = self.status()
        self.assertEqual(out["outcome"], "idle")                               # only a user answer is left
        self.assertTrue(any("parked" in w for w in out["waiting"]))
        os.remove(os.path.join(self.feat, "open-questions", "agg-order.md"))
        self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=0)   # un-parked: reuses its worktree
        self.commit(os.path.join(self.tmp, "wt", "agg-order"), "src/a.txt", "a\n")
        self.review("agg-order")
        self.compose("start", "agg-order", expect=0)
        self.compose("promote", "agg-order", expect=0)
        for bid in ("svc-order", "rm-orders", "svc-report"):
            self.run_tool("move", self.feat, bid, "--to", "doing", expect=0)
            self.integrate(bid)
        for bid in ("agg-order", "svc-order", "rm-orders", "svc-report"):
            self.run_tool("move", self.feat, bid, "--to", "done", expect=0)
        out = self.status()
        self.assertEqual(out["outcome"], "idle")                               # both releases await the user
        self.assertIn("release R0: releasable, awaiting the user's confirmation (`release confirm`)", out["waiting"])
        self.put("pre-release.md", "- [ ] R1 · rm-orders · MED · a.py:1 · x · v · d\n")
        self.assertEqual(self.status()["outcome"], "work")                     # R1 is done: its MED is work
        self.put("pre-release.md", "- [~] R1 · rm-orders · MED · a.py:1 · x · v · d · waived: ok\n")
        self.assertEqual(self.status()["outcome"], "work")                     # a legacy waiver frees nothing
        self.put("pre-release.md", "- [ ] R1 · rm-orders · MED · a.py:1 · x · v · d\n")
        h = mismagent.finding_id(["R1", "rm-orders", "MED", "a.py:1", "x", "v", "d"])
        self.run_tool("release", "waive", self.feat, "R1", "--entries", json.dumps([dict(
            line=1, finding=h, by="Ada", consent="msg-7", reason="cosmetic", risk="none", revisit="R2")]), expect=0)
        self.put("tasks/be/backlog/s.md", "---\nid: s\ntype: spike\n---\n# S\n")
        self.assertEqual(self.status()["outcome"], "idle")                     # a spike waits on a decision
        self.put("tasks/be/backlog/s.md", "---\nid: s\ntype: spike\ncentral: true\n---\n# S\n")
        self.assertEqual(self.status()["outcome"], "work")
        os.remove(os.path.join(self.feat, "tasks", "be", "backlog", "s.md"))
        self.put("tasks/be/backlog/c.md", "---\nid: c\ntype: cleanup\nready_when: \"no-consumer-uses:X\"\n---\n")
        self.assertEqual(self.status()["outcome"], "idle")                     # waits on its condition
        os.remove(os.path.join(self.feat, "tasks", "be", "backlog", "c.md"))
        self.assertEqual(self.status()["outcome"], "idle")                     # awaiting confirmation
        self.put("integrated/ghost.json", json.dumps({"sha": "0" * 40}))
        self.assertEqual(self.status(expect=1)["outcome"], "anomaly")


    def all_done(self):
        self.finish("scaffold-app")
        blocks = ("agg-order", "svc-order", "rm-orders", "svc-report")
        for bid in blocks:
            self.run_tool("move", self.feat, bid, "--to", "doing", expect=0)
            self.integrate(bid)
        for bid in blocks:
            self.run_tool("move", self.feat, bid, "--to", "done", expect=0)
        self.assertEqual(self.status()["outcome"], "idle")                     # releases await confirmation

    def test_terminal_outcome_runs_lint_first(self):
        self.all_done()
        self.put("context-map.md", "# Map\n\n## Open spikes\n- [ ] sync: q — owner: shop — central: true\n",
                 base=self.out)                                                  # a central spike, no node
        out = self.status(expect=1)
        self.assertEqual(out["outcome"], "anomaly")
        self.assertIn(("lint_gap", "spikes.central_node"), {(x["kind"], x["id"]) for x in out["anomalies"]})

    def test_cycle_or_missing_scaffold_file_is_an_anomaly_not_idle(self):
        self.write_feature(MANIFEST.replace("    related_adrs: [0001]\n", "    related_adrs: [0001]\n    after: [svc-order]\n"))
        self.finish("scaffold-app")
        out = self.status(expect=1)
        self.assertEqual((out["outcome"], out["anomalies"][0]["id"]), ("anomaly", "after.cycle"))
        self.write_feature(MANIFEST, skip=("scaffold-app",))
        shutil.rmtree(os.path.join(self.feat, "integrated"))
        out = self.status(expect=1)
        self.assertIn(("lint_gap", "blockfile.exists"), {(x["kind"], x["id"]) for x in out["anomalies"]})

    def test_central_spike_in_doing_is_idle_only_with_evidence(self):
        self.all_done()
        self.put("tasks/be/doing/s.md", "---\nid: s\ntype: spike\ncentral: true\n---\n# S\n")
        out = self.status(expect=1)                                            # no evidence, no worktree
        self.assertEqual((out["outcome"], out["anomalies"][0]["kind"]), ("anomaly", "doing_without_worktree"))
        wt = os.path.join(self.tmp, "wt", "spike-s")
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "spike/s", wt, "feature/shop")
        self.assertEqual(self.status()["outcome"], "work")                     # the prototype is running
        sh(self.repo, "git", "worktree", "remove", "--force", wt)
        self.put("spikes/s.md", "evidence\n")
        self.assertEqual(self.status()["outcome"], "idle")                     # waits on the user's closure


def fline(rel, bid, sev, loc, issue, mark=" "):
    """A pre-release.md line and its finding id."""
    fields = [rel, bid, sev, loc, issue, "verifier", "2026-09-24"]
    return "- [%s] %s\n" % (mark, " · ".join(fields)), mismagent.finding_id(fields)


class TestV023(Base):
    """v0.23: the release path — findings, evaluation, records, groups, confirm; resume; release scope."""

    def status(self, expect=0):
        return self.run_tool("status", self.feat, "--integration", "feature/shop", expect=expect)

    def rlist(self, rn):
        return self.run_tool("release", "list", self.feat, rn, "--integration", "feature/shop", expect=0)

    def all_done(self):
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.integrate("scaffold-app")
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        blocks = ("agg-order", "svc-order", "rm-orders", "svc-report")
        for bid in blocks:
            self.run_tool("move", self.feat, bid, "--to", "doing", expect=0)
            self.integrate(bid)
        for bid in blocks:
            self.run_tool("move", self.feat, bid, "--to", "done", expect=0)

    def findings(self, *lines):
        out = [fline(*l) for l in lines]
        self.put("pre-release.md", "# Pre-release\n\n" + "".join(t for t, _ in out))
        return [h for _, h in out]                 # line n of the file = index n-3

    def act(self, op, rn, entries, expect):
        return self.run_tool("release", op, self.feat, rn, "--entries", json.dumps(entries), expect=expect)

    def waiver(self, line, h, **kw):
        return dict(dict(line=line, finding=h, by="Ada", consent="chat 2026-09-24 12:03", reason="cosmetic",
                         risk="a darker banner", revisit="before R2"), **kw)

    # -- core ----------------------------------------------------------------------------------------
    def test_findings_identity_is_the_seven_fields_not_the_line(self):
        self.put("pre-release.md", "x\n" + fline("R0", "agg-order", "MED", "src/a.py#Order.total", "i")[0] +
                 "- [ ] R0 · agg-order · MED · src/a.py:3,9 · a list · v · d\n- [ ] R0 · agg-order · MED · a.py:1\n"
                 "- [x] R0 · agg-order · MID · a.py:1 · i · v · d\n")
        f = mismagent.parse_findings(mismagent.Feature(self.feat))
        self.assertEqual((f[0]["line"], f[0]["locator"]), (2, "src/a.py#Order.total"))
        self.assertEqual(f[0]["finding"], fline("R0", "agg-order", "MED", "src/a.py#Order.total", "i", "x")[1])
        self.assertEqual([("error" in x) for x in f], [False, True, True, True])   # locator, fields, severity
        rules = {g["rule"] for g in self.gaps()[1]["gaps"]}
        self.assertIn("release.finding", rules)

    def test_policy_med_blocks_low_is_advisory_and_a_view_for_later_releases(self):
        self.all_done()
        h = self.findings(("R0", "agg-order", "LOW", "a.py:1", "rename"), ("R0", "svc-order", "MED", "b.py:2", "split"),
                          ("R1", "rm-orders", "LOW", "c.py:3", "tidy"))
        r0 = self.rlist("R0")
        self.assertEqual(([b["finding"] for b in r0["blocking"]], [a["finding"] for a in r0["advisory"]]), ([h[1]], [h[0]]))
        self.assertFalse(r0["releasable"])
        self.assertEqual(r0["sha"], sh(self.repo, "git", "rev-parse", "feature/shop"))
        r1 = self.rlist("R1")
        self.assertTrue(r1["releasable"])                                     # a LOW never blocks
        self.assertEqual([(a["release"], a["finding"]) for a in r1["advisory"]], [("R0", h[0]), ("R1", h[2])])
        self.assertEqual(mismagent.read(os.path.join(self.feat, "pre-release.md")).count("rename"), 1)   # never copied
        self.assertIn("release R0: 1 blocking lines (`release list`)", self.status()["work"])
        self.act("waive", "R0", [self.waiver(4, h[1])], 0)
        r0 = self.rlist("R0")
        self.assertTrue(r0["releasable"])
        self.assertEqual((r0["waived"][0]["by"], r0["waived"][0]["revisit"]), ("Ada", "before R2"))
        self.assertIn("- [~] R0 · svc-order · MED", mismagent.read(os.path.join(self.feat, "pre-release.md")))
        rec = mismagent.read(os.path.join(self.feat, "release-decisions", "R0.md"))
        recs = json.loads(re.search(r"```json\n(.*?)```", rec, re.S).group(1))["records"]
        self.assertEqual((recs[0]["action"], recs[0]["finding"], recs[0]["consent"]), ("waive", h[1], "chat 2026-09-24 12:03"))
        self.assertTrue(recs[0]["at"].endswith("Z"))
        self.run_tool("lint", self.feat, expect=0)

    def test_release_without_blocks_waits_and_status_is_idle(self):
        self.write_feature(MANIFEST + '  R2: { goal: "later", blocks: [] }\n')   # declared, no block rows
        self.all_done()
        self.findings(("R2", "agg-order", "MED", "a.py:1", "for later"))
        r2 = self.rlist("R2")
        self.assertEqual((r2["blocks"], r2["waiting"], r2["releasable"]), ([], ["R2 has no blocks"], False))
        out = self.status()
        self.assertEqual(out["outcome"], "idle")                              # #47: nothing actionable
        self.assertIn("release R2: no blocks (1 blocking lines wait)", out["waiting"])
        self.assertFalse(any("R2" in w for w in out["work"]))

    def test_orphan_and_legacy_marks_free_nothing_and_lint_says_so(self):
        self.all_done()
        self.put("pre-release.md", "# P\n\n" + fline("R0", "agg-order", "MED", "a.py:1", "x", "~")[0].rstrip("\n") +
                 " · waived: ok\n" + fline("R0", "svc-order", "MED", "b.py:1", "y", "x")[0])
        self.put("release-decisions/R0.md", "# R0\n\nThe user waived line 3 in chat.\n")   # a legacy file
        r0 = self.rlist("R0")
        self.assertEqual(len(r0["blocking"]), 2)
        self.assertIn("legacy waiver", r0["blocking"][0]["reason"])
        gaps = self.gaps()[0]
        self.assertIn(("release.unverified", "pre-release.md line 3"), gaps)
        self.assertIn(("release.unverified", "pre-release.md line 4"), gaps)
        h = fline("R0", "agg-order", "MED", "a.py:1", "x")[1]
        self.act("waive", "R0", [self.waiver(3, h)], 0)                       # re-recorded by the tool
        text = mismagent.read(os.path.join(self.feat, "release-decisions", "R0.md"))
        self.assertIn("The user waived line 3 in chat.", text)                # legacy prose kept
        self.assertIn("· waived: ok", mismagent.read(os.path.join(self.feat, "pre-release.md")))
        self.assertEqual(len(self.rlist("R0")["blocking"]), 1)
        self.put("pre-release.md", "# P\n\n" + fline("R0", "agg-order", "MED", "a.py:1", "x")[0])   # mark removed
        self.assertIn(("release.record_orphan", "pre-release.md line 3"), self.gaps()[0])

    def test_a_batch_is_validated_whole_before_any_write(self):
        self.all_done()
        h = self.findings(("R0", "agg-order", "MED", "a.py:1", "x"), ("R0", "svc-order", "HIGH", "b.py:1", "y"),
                          ("R1", "rm-orders", "MED", "c.py:1", "z"))
        before = mismagent.read(os.path.join(self.feat, "pre-release.md"))
        bad = [[self.waiver(3, h[0]), self.waiver(4, h[1])],                  # a HIGH is never waived
               [self.waiver(3, h[0]), self.waiver(3, h[0])],                  # twice
               [self.waiver(3, h[1])],                                        # stale selector: line 3 is another finding
               [self.waiver(5, h[2])],                                        # another release
               [self.waiver(3, h[0], extra="x")], [dict(self.waiver(3, h[0]), by="")]]
        for entries in bad:
            out = self.act("waive", "R0", entries, 1)
            self.assertEqual(out["refused"], "nothing written", entries)
        self.assertEqual(mismagent.read(os.path.join(self.feat, "pre-release.md")), before)
        self.assertFalse(os.path.exists(os.path.join(self.feat, "release-decisions")))
        self.run_tool("release", "waive", self.feat, "R0", "--entries", "[]", expect=2)
        self.run_tool("release", "waive", self.feat, "R0", expect=2)          # --entries required

    def test_close_needs_fresh_evidence_and_a_code_change_stales_it(self):
        self.all_done()
        h = self.findings(("R0", "agg-order", "MED", "src/agg-order.txt:1", "x"))[0]
        tip = sh(self.repo, "git", "rev-parse", "feature/shop")
        entry = dict(line=3, finding=h, sha=tip, by="mismagent-verifier", evidence="release-evidence/R0.md#" + h)
        self.assertIn("release-evidence", self.act("close", "R0", [entry], 1)["problems"][0])
        self.put("release-evidence/R0.md", "# R0\n\n## other\n")
        self.assertIn("does not name", self.act("close", "R0", [entry], 1)["problems"][0])
        self.put("release-evidence/R0.md", "# R0\n\n## %s\nsha %s · src/agg-order.txt · test run: green\n" % (h, tip))
        self.assertIn("not a commit", self.act("close", "R0", [dict(entry, sha="f" * 40)], 1)["problems"][0])
        self.act("close", "R0", [entry], 0)
        self.assertTrue(self.rlist("R0")["releasable"])
        self.line_commit("notes.txt", "records only\n")                     # another file: still fresh
        self.assertTrue(self.rlist("R0")["releasable"])
        self.line_commit("src/agg-order.txt", "changed\n")                   # the verified code changed
        r0 = self.rlist("R0")
        self.assertFalse(r0["releasable"])
        self.assertIn("changed after the closure", r0["blocking"][0]["reason"])
        self.act("close", "R0", [dict(entry, sha="feature/shop")], 0)        # verified again: a new record
        self.assertTrue(self.rlist("R0")["releasable"])
        self.run_tool("lint", self.feat, expect=0)

    def test_group_writes_one_rework_file_and_one_deduplicated_pack(self):
        self.all_done()
        h = self.findings(("R0", "agg-order", "MED", "a.py:1", "x"), ("R0", "svc-order", "MED", "b.py:1", "y"),
                          ("R1", "svc-report", "MED", "c.py:1", "z"), ("R1", "rm-orders", "MED", "d.py:1", "w"))
        L = lambda n: "%d:%s" % (n, h[n - 3])                                # line:finding pairs
        self.run_tool("release", "group", self.feat, "R0", "--id", "grp-1", "--lines", L(3), expect=2)
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", expect=2)
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", "3", expect=2)   # a bare number
        out = self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", "3:" + h[1], expect=1)
        self.assertIn("re-read `release list`", out["problems"][0])          # the line is now another finding
        out = self.run_tool("release", "group", self.feat, "R1", "--id", "pre-R1-1", "--lines", L(5), L(6), expect=1)
        self.assertIn("contexts orders, reports", out["problems"][0])       # one group per (context, side)
        out = self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", L(3), L(4), expect=0)
        self.assertEqual((out["blocks"], out["findings"]), (["agg-order", "svc-order"], h[:2]))
        text = mismagent.read(out["file"])
        self.assertTrue(text.startswith("---\nrelease: R0\nblocks: [agg-order, svc-order]\nfindings: [%s, %s]\n---\n"
                                        % tuple(h[:2])))
        self.assertIn("- [ ] R0 · svc-order · MED · b.py:1 · y", text)
        self.assertTrue(self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", L(3), L(4),
                                      expect=0)["unchanged"])
        out = self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-2", "--lines", L(3), expect=1)
        self.assertIn("already in group pre-R0-1", out["problems"][0])
        md = self.run_tool("pack", self.feat, "pre-R0-1", expect=0)
        self.assertEqual(md.count("\n## Boundary b-order\n"), 1)           # consumed by both, packed once
        for sec in ("## Rework pre-R0-1-1", "## Block agg-order", "## Block svc-order"):
            self.assertIn(sec, md)
        self.assertNotIn("## Open findings", md)
        h0 = self.spec_hash("pre-R0-1")
        self.write_feature(MANIFEST.replace("sku:string · qty:int", "sku:string · qty:int · note:string"))
        self.assertNotEqual(self.spec_hash("pre-R0-1"), h0)                 # a contract change stales the group

    def test_release_scope_is_validated_before_writing_and_selects_the_group_pack(self):
        note = ("### D-%04d · %s\n- Meta: 2026-09-24; scope: %s; status: %s\n- Question: q?\n- Options: A; B.\n"
                "- Hypothesis: n/a — decided by REQ-1\n- Check: n/a — decided by REQ-1\n- Result: n/a — decided by REQ-1\n"
                "- Debate: none\n- Decision: %s\n- By: decided: user; recorded: worker-composer\n"
                "- Docs: [m](building-blocks.yaml)\n- Revisit: never\n%s")
        notes = os.path.join(self.feat, "decisions.md")
        self.put("e.md", note % (1, "Bad scope", "block:pre-R0-1", "accepted", "old", ""))
        out = self.run_tool("why", "append", notes, "--entry", os.path.join(self.feat, "e.md"), expect=1)
        self.assertEqual(out["errors"][0]["rule"], "meta.scope")
        self.assertFalse(os.path.exists(notes))                              # refused before writing
        self.put("e.md", note % (1, "Unknown release", "release:R9", "accepted", "old", ""))
        self.run_tool("why", "append", notes, "--entry", os.path.join(self.feat, "e.md"), expect=1)
        self.put("decisions.md", note % (1, "Bad scope", "block:pre-R0-1", "accepted", "old", ""))   # history as found
        self.assertIn(("why.scope", "decisions.md D-0001"), self.gaps()[0])
        self.put("e.md", note % (2, "Release scope", "release:R0", "accepted", "keep the rename", "- Supersedes: D-0001\n"))
        self.run_tool("why", "append", notes, "--entry", os.path.join(self.feat, "e.md"), expect=0)
        self.run_tool("lint", self.feat, expect=0)                           # superseded, not rewritten
        h = self.findings(("R0", "agg-order", "MED", "a.py:1", "x"))[0]
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", "3:" + h, expect=0)
        self.assertIn("keep the rename", self.run_tool("pack", self.feat, "pre-R0-1", expect=0))
        self.assertNotIn("keep the rename", self.run_tool("pack", self.feat, "agg-order", expect=0))

    # -- resume --------------------------------------------------------------------------------------
    def test_a_doing_block_is_a_resume_candidate_never_diagnosed(self):
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.integrate("scaffold-app")
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=0)
        wt = self.block_wt("agg-order")
        self.put("src/half.py", "work in progress\n", base=wt)
        out = self.status()
        self.assertEqual(out["outcome"], "work")
        self.assertEqual(out["resume"], [{"id": "agg-order", "branch": "block/agg-order", "worktree": wt, "uncommitted": 1,
                                          "attempt": 1, "commits": 0, "handoff": None, "result": None}])
        self.assertIn("resume: agg-order (doing, not integrated; worktree %s, 1 uncommitted, attempt 1, 0 commits, "
                      "no return)" % wt, out["work"])
        self.assertNotIn("interrupt", json.dumps(out))
        self.assertEqual(self.run_tool("ready", self.feat, expect=0)["resume"], out["resume"])
        self.assertEqual(mismagent.read(os.path.join(wt, "src", "half.py")), "work in progress\n")   # untouched

    def test_a_resume_entry_tells_a_returned_worker_from_an_interrupted_one(self):
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.integrate("scaffold-app")
        self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        self.run_tool("move", self.feat, "agg-order", "--to", "doing", expect=0)
        wt = self.block_wt("agg-order")
        self.commit(wt, "src/a.py", "ac1\n")
        self.commit(wt, "src/b.py", "ac2\n")
        r = self.status()["resume"][0]
        self.assertEqual((r["attempt"], r["commits"], r["handoff"]), (1, 2, None))      # interrupted, work committed
        h = self.put(os.path.join(".worktrees", "returns", os.path.basename(self.feat), "agg-order-1.md"), "entries\n",
                     base=self.repo)
        r = self.status()["resume"][0]
        self.assertEqual((r["handoff"], r["result"]), (h, None))                       # entries so far, no return
        self.put(h, "entries\nRESULT: CHECKPOINT\n\nmore\nRESULT: READY-FOR-REVIEW\nBLOCK: agg-order\n", base=self.repo)
        self.assertEqual(self.status()["resume"][0]["result"], "READY-FOR-REVIEW")      # returned: review it
        self.put("rework/agg-order-1.md", "# Rework agg-order — cycle 1\n")
        r = self.status()["resume"][0]
        self.assertEqual((r["attempt"], r["handoff"], r["result"]), (2, None, None))                       # the rework has not returned

    def test_a_later_release_consumer_is_neither_an_earlier_blocks_spec_nor_its_weld(self):
        feat = lambda: mismagent.Feature(self.feat)
        h = {b: mismagent.spec_hash(feat(), b) for b in ("agg-order", "svc-order", "rm-orders")}
        self.put("building-blocks.yaml", MANIFEST.replace("consumers: [svc-order, rm-orders]", "consumers: [svc-order]"))
        self.assertEqual(mismagent.spec_hash(feat(), "agg-order"), h["agg-order"])    # R1 consumer: not the R0 owner's
        self.assertEqual(mismagent.spec_hash(feat(), "svc-order"), h["svc-order"])    # another consumer never binds it
        self.put("building-blocks.yaml", MANIFEST.replace("consumers: [svc-order, rm-orders]", "consumers: [rm-orders]"))
        self.assertNotEqual(mismagent.spec_hash(feat(), "agg-order"), h["agg-order"])  # its own release's consumer is
        self.put("building-blocks.yaml", MANIFEST)
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.integrate("scaffold-app")
        for b in ("agg-order", "svc-order"):
            self.integrate(b)
        self.assertTrue(feat().finishable("agg-order"))       # rm-orders (R1) not integrated: R0 still finishes
        self.assertTrue(feat().finishable("svc-order"))
        self.assertFalse(feat().welded(feat().bnd["b-order"]))

    def test_a_later_releases_work_as_a_note_on_an_earlier_block_is_a_lint_gap(self):
        self.put("building-blocks.yaml", MANIFEST.replace("    commands: [PlaceOrder]\n",
                 "    commands: [PlaceOrder]\n    notes: \"R1 extends this query in place\"\n", 1))
        self.assertIn(("release.later_work", "svc-order"), self.gaps()[0])
        self.move("svc-order", "done")
        self.assertNotIn(("release.later_work", "svc-order"), self.gaps()[0])        # history, never reopened

    def test_a_release_refusal_names_the_unexpected_and_the_missing_flags(self):
        out = self.run_tool("release", "close", self.feat, "R0", "--entries", "[]", "--integration", "feature/shop")
        self.assertIn("not an option of close: --integration", out["error"])
        out = self.run_tool("release", "list", self.feat, "R0")
        self.assertIn("missing: --integration", out["error"])

    def test_a_proof_recorded_on_the_full_consumer_list_stays_valid(self):
        feat = mismagent.Feature(self.feat)
        full = mismagent.spec_hash(feat, "agg-order", own=False)
        self.assertTrue(mismagent.spec_current(feat, "agg-order", full))
        self.assertFalse(mismagent.spec_current(feat, "agg-order", "0" * 64))

    def test_a_state_move_rewrites_the_decision_links_to_the_moved_file(self):
        class F:
            dir = self.feat
        self.put("decisions.md", "- Docs: [q](open-questions/q1.md), [s](./tasks/app/backlog/s1.md#result), "
                                 "[other](open-questions/q10.md)\n")
        j = lambda *x: os.path.join(self.feat, *x)
        self.assertEqual(mismagent.relink_notes(F, j("open-questions", "q1.md"), j("open-questions", "closed", "q1.md")), 1)
        self.assertEqual(mismagent.relink_notes(F, j("tasks", "app", "backlog", "s1.md"), j("tasks", "app", "done", "s1.md")), 1)
        self.assertEqual(mismagent.read(j("decisions.md")), "- Docs: [q](open-questions/closed/q1.md), "
                         "[s](tasks/app/done/s1.md#result), [other](open-questions/q10.md)\n")

    # -- confirm (git) -------------------------------------------------------------------------------
    def releasable_line(self):
        """Every block done, F committed on feature/shop, checked out in the main checkout."""
        self.all_done()
        sh(self.repo, "git", "config", "tag.gpgSign", "false")
        base = sh(self.repo, "git", "rev-parse", "main")
        sh(self.repo, "git", "checkout", "-q", "feature/shop")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "-m", "records")
        return sh(self.repo, "git", "rev-parse", "HEAD"), base

    def confirm(self, rn, expect, **kw):
        args = dict({"integration": "feature/shop", "tag": "shop-" + rn, "merge-to": "main", "by": "Ada",
                     "consent": "chat 2026-09-24 12:10"}, **kw)
        return self.run_tool("release", "confirm", self.feat, rn, *[x for k, v in args.items()
                                                                    for x in ("--" + k, v)], expect=expect)

    def test_confirm_fast_forwards_the_base_and_tags_idempotently(self):
        S, T = self.releasable_line()
        self.assertIn("release R0: releasable, awaiting the user's confirmation (`release confirm`)", self.status()["waiting"])
        self.run_tool("release", "confirm", self.feat, "R0", "--integration", "feature/shop", "--sha", S, "--tag", "t",
                      "--merge-to", "main", "--base-sha", T, "--by", "Ada", expect=2)          # no consent
        out = self.confirm("R0", 0, sha=S, **{"base-sha": T})
        self.assertEqual((out["confirmed"], out["partial"], out["unchanged"]), (True, [], False))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "main"), S)
        tag = sh(self.repo, "git", "cat-file", "-p", "shop-R0")
        for want in ("object " + S, "mismagent-release: shop/R0", "merge-to: main (from %s)" % T, "decided: Ada",
                     "consent: chat 2026-09-24 12:10", "integration: feature/shop @ " + S):
            self.assertIn(want, tag)
        self.assertTrue(self.confirm("R0", 0, sha=S, **{"base-sha": T})["unchanged"])   # identical repeat
        self.assertEqual(self.rlist("R0")["confirmed"]["tag"], "shop-R0")
        self.assertNotIn("R0", json.dumps(self.status()["waiting"]))
        out = self.confirm("R1", 0, sha=S, **{"base-sha": S})               # the base already holds S
        self.assertEqual(self.status()["outcome"], "done")
        sh(self.repo, "git", "tag", "-d", "shop-R1")                          # partial: the tag is missing
        out = self.confirm("R1", 0, sha=S, **{"base-sha": S})
        self.assertIn("only the tag is created", out["partial"][0])
        sh(self.repo, "git", "update-ref", "refs/heads/main", T)              # partial: the merge is missing
        self.assertEqual(self.status()["outcome"], "idle")                    # a tag alone is no confirmation
        out = self.confirm("R0", 0, sha=S, **{"base-sha": T})
        self.assertIn("only the fast-forward is done", out["partial"][0])
        self.assertEqual(sh(self.repo, "git", "rev-parse", "main"), S)

    def test_confirm_preflight_refuses_and_writes_nothing(self):
        S, T = self.releasable_line()
        sh(self.repo, "git", "tag", "taken", T)
        cases = [({"sha": T, "base-sha": T}, "not the consented"),
                 ({"sha": S, "base-sha": S}, "neither the consented base"),
                 ({"sha": S, "base-sha": T, "tag": "taken"}, "collision"),
                 ({"sha": S, "base-sha": T, "consent": " "}, "--consent"),
                 ({"sha": S, "base-sha": T, "merge-to": "feature/shop"}, "integration line itself")]
        for kw, why in cases:
            out = self.confirm("R0", 1, **kw)
            self.assertIn(why, " ".join(out["problems"]), kw)
        self.put("stray.txt", "x\n", base=self.repo)
        self.assertIn("uncommitted", " ".join(self.confirm("R0", 1, sha=S, **{"base-sha": T})["problems"]))
        os.remove(os.path.join(self.repo, "stray.txt"))
        wt = os.path.join(self.tmp, "wt", "main")
        sh(self.repo, "git", "worktree", "add", "-q", wt, "main")
        self.commit(wt, "hotfix.txt", "x\n")                                  # the base diverged
        T2 = sh(wt, "git", "rev-parse", "HEAD")
        self.assertIn("diverged", " ".join(self.confirm("R0", 1, sha=S, **{"base-sha": T2})["problems"]))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "main"), T2)
        self.assertEqual(sh(self.repo, "git", "tag", "-l", "shop-*"), "")
        self.findings(("R0", "agg-order", "MED", "a.py:1", "x"))
        self.assertIn("not releasable", " ".join(self.confirm("R0", 1, sha=S, **{"base-sha": T})["problems"]))

    def test_confirm_on_a_checked_out_base_fast_forwards_that_checkout(self):
        S, T = self.releasable_line()
        wt = os.path.join(self.tmp, "wt", "main")
        sh(self.repo, "git", "worktree", "add", "-q", wt, "main")
        self.confirm("R0", 0, sha=S, **{"base-sha": T})
        self.assertEqual(sh(wt, "git", "rev-parse", "HEAD"), S)
        self.assertEqual(sh(wt, "git", "status", "--porcelain"), "")

    # -- review fixes: shared evaluation, tag identity, preflight, repair path --------------------------
    def records(self, rn, *recs):
        self.put("release-decisions/%s.md" % rn, "# %s\n\n```json\n%s\n```\n" % (rn, json.dumps({"records": list(recs)})))

    def test_an_integrated_record_off_the_line_is_not_releasable_and_confirm_refuses(self):
        _, T = self.releasable_line()
        wt = os.path.join(self.tmp, "wt", "side")
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "side", wt, "main")
        off = self.commit(wt, "side.txt", "x\n")                              # a commit never on B
        rec = json.loads(mismagent.read(os.path.join(self.feat, "integrated", "agg-order.json")))
        self.put("integrated/agg-order.json", json.dumps(dict(rec, sha=off)))
        sh(self.repo, "git", "commit", "-q", "-am", "record off the line")
        S = sh(self.repo, "git", "rev-parse", "HEAD")
        r0 = self.rlist("R0")
        self.assertFalse(r0["releasable"])
        self.assertIn("block agg-order: done, its integrated sha is not on the line", r0["waiting"])
        out = self.confirm("R0", 1, sha=S, **{"base-sha": T})
        self.assertIn("not releasable", " ".join(out["problems"]))
        self.assertEqual((sh(self.repo, "git", "rev-parse", "main"), sh(self.repo, "git", "tag", "-l")), (T, ""))

    def test_a_tag_of_another_destination_or_consent_is_a_collision(self):
        S, T = self.releasable_line()
        self.confirm("R0", 0, sha=S, **{"base-sha": T})
        sh(self.repo, "git", "branch", "production", T)
        out = self.confirm("R0", 1, sha=S, **{"base-sha": T, "merge-to": "production"})
        self.assertIn("collision", " ".join(out["problems"]))
        self.assertIn("merge-to main", " ".join(out["problems"]))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "production"), T)   # nothing written
        out = self.confirm("R0", 1, sha=S, **{"base-sha": T, "consent": "another message"})
        self.assertIn("collision", " ".join(out["problems"]))
        self.assertTrue(self.confirm("R0", 0, sha=S, **{"base-sha": T})["unchanged"])

    def test_an_invalid_tag_name_is_refused_before_the_fast_forward(self):
        S, T = self.releasable_line()
        out = self.confirm("R0", 1, sha=S, **{"base-sha": T, "tag": "bad tag"})
        self.assertIn("not a valid tag name", " ".join(out["problems"]))
        self.assertEqual(sh(self.repo, "git", "rev-parse", "main"), T)

    def test_record_mark_gaps_are_in_the_shared_evaluation_and_are_composer_work(self):
        self.all_done()
        self.assertTrue(self.rlist("R0")["releasable"])
        self.records("R0", dict(self.waiver(3, "abcdef012345"), action="waive", at="2026-09-24T12:00:00Z"))
        r0 = self.rlist("R0")
        self.assertFalse(r0["releasable"])
        self.assertIn("release.record_orphan", r0["gaps"][0])
        out = self.status()
        self.assertEqual(out["outcome"], "work")
        self.assertIn("release R0: 1 record/mark gaps to repair (`lint`)", out["work"])

    def test_an_invalid_record_is_repaired_only_by_replace(self):
        self.all_done()
        h = self.findings(("R0", "agg-order", "MED", "a.py:1", "x", "~"))[0]
        bad = dict(self.waiver(3, h), action="waive", at="2026-09-24T12:00:00Z")
        del bad["by"]
        self.records("R0", bad)
        self.run_tool("lint", self.feat, expect=1)
        out = self.act("waive", "R0", [self.waiver(3, h)], 1)                  # a plain re-record never repairs
        self.assertIn("--replace %s" % h, " ".join(out["problems"]))
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", "3:" + h, "--replace", h,
                      expect=2)
        out = self.run_tool("release", "waive", self.feat, "R0", "--entries", json.dumps([self.waiver(3, h)]),
                            "--replace", "0" * 12, expect=1)
        self.assertIn("not a finding of the batch", " ".join(out["problems"]))
        out = self.run_tool("release", "waive", self.feat, "R0", "--entries", json.dumps([self.waiver(3, h)]),
                            "--replace", h, expect=0)
        self.assertEqual(out["replaced"], [h])
        recs = json.loads(re.search(r"```json\n(.*?)```", mismagent.read(out["file"]), re.S).group(1))["records"]
        self.assertEqual([r["by"] for r in recs], ["Ada"])
        self.run_tool("lint", self.feat, expect=0)
        self.assertTrue(self.rlist("R0")["releasable"])


COMP = "    consumes: [b-order]\n    commands: [PlaceOrder]\n"   # svc-order's row, the R0 composition block
ARCH = "# Architecture\n\n- `composition_root: src/app/main`\n"


class TestV024(Base):
    """v0.24: the composition block, the worker's checkpoint (`progress record`), the pack diet."""

    def comp(self, extra="    composition: true\n    after: [agg-order]\n", base=MANIFEST):
        return base.replace(COMP, COMP + extra)

    def status(self, expect=0):
        return self.run_tool("status", self.feat, "--integration", "feature/shop", expect=expect)

    def record(self, bid, cp=None, head=None, h=None, expect=0):
        cp = json.dumps({"done": ["INV-1 green"], "next": "the rejection path"} if cp is None else cp)
        return self.run_tool("progress", "record", self.feat, bid, "--head", head or "block/" + bid,
                             "--spec-hash", h or self.spec_hash(bid), "--json", cp, expect=expect)

    # -- composition ---------------------------------------------------------------------------------
    def test_composition_lint_unique_last_root_and_legacy(self):
        self.run_tool("lint", self.feat, expect=0)                           # no flag: no new gap
        self.write_feature(self.comp("    composition: true\n"))
        gaps, out = self.gaps()
        self.assertIn(("composition.last", "svc-order"), gaps)                # agg-order is its R0 sibling
        self.assertIn(("composition.root", "architecture.md"), gaps)
        self.assertEqual({g["rule"]: g["bounce_to"] for g in out["gaps"]}["composition.root"], "architect")
        self.put("architecture.md", ARCH, base=self.out)
        self.write_feature(self.comp())
        self.run_tool("lint", self.feat, expect=0)
        m = self.comp().replace("    related_adrs: [0001]\n", "    related_adrs: [0001]\n    composition: true\n")
        self.write_feature(m)
        self.assertIn(("composition.unique", "agg-order, svc-order"), self.gaps()[0])
        m = self.comp().replace("    related_adrs: [0001]\n", "    related_adrs: [0001]\n    side: fe\n")
        self.write_feature(m.replace("    composition: true\n    after: [agg-order]\n", "    composition: true\n"))
        self.run_tool("lint", self.feat, expect=0)                           # another side: not a sibling
        self.write_feature(self.comp("    composition: yes\n"))
        self.assertIn(("composition.valid", "svc-order"), self.gaps()[0])
        self.write_feature(MANIFEST.replace("    wave: 0\n", "    wave: 0\n    composition: true\n", 1))
        self.assertIn(("composition.valid", "scaffold-app"), self.gaps()[0])
        for r in ("composition.unique", "composition.last", "composition.root"):
            self.assertIn(r, mismagent.TERMINAL_LINT)

    def test_composition_render_line_frontmatter_and_spec_hash(self):
        h = self.spec_hash("svc-order")
        self.write_feature(self.comp())
        self.assertNotEqual(self.spec_hash("svc-order"), h)                   # the flag is spec
        shutil.rmtree(os.path.join(self.feat, "blocks"))
        self.put("building-blocks.yaml", self.comp(base=RENDERED))
        self.run_tool("manifest", "render", self.feat, expect=0)
        path = os.path.join(self.feat, "blocks", "orders", "todo", "svc-order.md")
        text = mismagent.read(path)
        self.assertIn("\ncomposition: true\n", text.split("\n---\n")[0] + "\n")
        self.assertIn("returns the id.\nComposition: extend the existing composition at <composition_root in "
                      "architecture.md> in place — never wrap it", text)
        self.assertIn(("composition.root", "architecture.md"), self.gaps()[0])
        self.put("architecture.md", ARCH, base=self.out)
        self.assertIn(("blockfile.render", "svc-order"), self.gaps()[0])       # the root is part of the render
        self.run_tool("manifest", "render", self.feat, expect=0)
        self.assertIn("composition at src/app/main in place", mismagent.read(path))
        self.run_tool("lint", self.feat, expect=0)
        self.assertNotIn("Composition:", mismagent.read(os.path.join(self.feat, "blocks", "orders", "todo",
                                                                      "agg-order.md")))

    # -- progress ------------------------------------------------------------------------------------
    def doing(self, bid):
        self.run_tool("move", self.feat, bid, "--to", "doing", expect=0)
        wt = self.block_wt(bid)
        self.commit(wt, "src/%s.txt" % bid, "one\n")
        return wt

    def test_progress_record_writes_atomically_and_counts_attempts(self):
        self.doing("agg-order")
        out = self.record("agg-order")
        self.assertEqual((out["ok"], out["id"], out["attempt"]), (True, "agg-order", 1))
        rec = json.loads(mismagent.read(out["file"]))
        self.assertEqual(out["file"], os.path.join(self.feat, "progress", "agg-order.json"))
        self.assertEqual(rec, {"head": sh(self.repo, "git", "rev-parse", "block/agg-order"),
                               "spec_hash": self.spec_hash("agg-order"), "attempt": 1,
                               "checkpoint": {"done": ["INV-1 green"], "next": "the rejection path"}, "extras": []})
        f = self.put("cp.json", json.dumps({"done": [], "next": "n", "tests": ["t1"], "decisions": "d"}), base=self.tmp)
        self.assertEqual(self.run_tool("progress", "record", self.feat, "agg-order", "--head", "block/agg-order",
                                       "--spec-hash", self.spec_hash("agg-order"), "--json", f, expect=0)["attempt"], 2)
        p = subprocess.run([sys.executable, TOOL, "progress", "record", self.feat, "agg-order", "--head", "block/agg-order",
                            "--spec-hash", self.spec_hash("agg-order"), "--json", "-"],
                           input='{"done": ["a"], "next": "b"}', capture_output=True, text=True)
        self.assertEqual((p.returncode, json.loads(p.stdout)["attempt"]), (0, 3))
        self.assertFalse(glob.glob(os.path.join(self.feat, "progress", "*.tmp")))

    def test_progress_record_refusals_write_nothing(self):
        self.doing("agg-order")
        self.record("agg-order")
        before = mismagent.read(os.path.join(self.feat, "progress", "agg-order.json"))
        h = self.spec_hash("agg-order")
        cases = [
            (dict(bid="ghost", h=h), "not a block of the manifest"),
            (dict(bid="agg-order", head="feature/shop"), "is not the tip of block/agg-order"),
            (dict(bid="agg-order", h="0" * 64), "not the block's current spec hash"),
            (dict(bid="svc-order", h=self.spec_hash("svc-order")), "not doing/"),
            (dict(bid="agg-order", cp={"done": "x", "next": "n"}), "`done`"),
            (dict(bid="agg-order", cp={"done": [], "next": " "}), "`next`"),
            (dict(bid="agg-order", cp={"done": [], "next": "n", "mood": "ok"}), "unknown keys mood"),
        ]
        for kw, why in cases:
            bid = kw.pop("bid")
            out = self.record(bid, expect=1, **kw)
            self.assertFalse(out["ok"])
            self.assertTrue(any(why in p for p in out["problems"]), (why, out))
        out = self.run_tool("progress", "record", self.feat, "agg-order", "--head", "block/agg-order",
                            "--spec-hash", h, "--json", "{bad", expect=1)
        self.assertIn("does not parse", out["problems"][0])
        self.assertEqual(mismagent.read(os.path.join(self.feat, "progress", "agg-order.json")), before)
        self.assertFalse(os.path.exists(os.path.join(self.feat, "progress", "svc-order.json")))

    def test_status_reports_progress_fresh_then_stale_and_pack_carries_only_a_fresh_one(self):
        wt = self.doing("agg-order")
        self.assertNotIn("progress", self.status()["resume"][0])
        self.assertNotIn("## Checkpoint", self.run_tool("pack", self.feat, "agg-order", expect=0))
        self.record("agg-order", {"done": ["INV-1 green"], "next": "the rejection path", "deviations": ["kept x"]})
        out = self.status()
        tip = sh(self.repo, "git", "rev-parse", "block/agg-order")
        self.assertEqual(out["resume"][0]["progress"], {"attempt": 1, "head": tip, "next": "the rejection path",
                                                        "fresh": True})
        self.assertTrue(any(w.endswith("; checkpoint attempt 1, fresh)") for w in out["work"]))
        md = self.run_tool("pack", self.feat, "agg-order", expect=0)
        self.assertLess(md.index("## Checkpoint — attempt 1"), md.index("## Block agg-order"))
        for s in ("- next: the rejection path", "  - INV-1 green", "- pending DEVIATIONS:\n  - kept x",
                  "source: `.mismagent/features/shop/progress/agg-order.json`"):
            self.assertIn(s, md)
        self.commit(wt, "src/more.txt", "more\n")                             # work after the checkpoint
        out = self.status()                                                  # stale: reported, no anomaly
        self.assertEqual((out["ok"], out["resume"][0]["progress"]["fresh"]), (True, False))
        self.assertNotIn("## Checkpoint", self.run_tool("pack", self.feat, "agg-order", expect=0))
        self.record("agg-order")                                             # recorded again at the new tip
        self.write_feature(MANIFEST.replace("never negative", "never negative nor absurd"))
        self.move("agg-order", "doing")
        self.assertFalse(self.status()["resume"][0]["progress"]["fresh"])     # the spec changed

    def test_an_integrated_block_ignores_its_progress_and_done_removes_it(self):
        self.run_tool("move", self.feat, "scaffold-app", "--to", "doing", expect=0)
        self.commit(self.block_wt("scaffold-app"), "src/s.txt", "s\n")
        self.record("scaffold-app")
        self.compose("start", "scaffold-app", expect=0)
        self.compose("promote", "scaffold-app", expect=0)
        self.assertEqual(self.status()["resume"], [])
        out = self.run_tool("move", self.feat, "scaffold-app", "--to", "done", expect=0)
        self.assertEqual(out["progress_removed"], os.path.join(self.feat, "progress", "scaffold-app.json"))
        self.assertFalse(os.path.exists(out["progress_removed"]))

    # -- pack diet -----------------------------------------------------------------------------------
    def test_pack_carries_only_the_findings_of_the_block_and_its_boundary_neighbours(self):
        lines = [fline("R0", "agg-order", "MED", "a.py:1", "owner of b-order"),
                 fline("R1", "rm-orders", "LOW", "r.py:1", "fellow consumer of b-order"),
                 fline("R0", "b-order", "MED", "b.py:1", "scoped to the boundary"),
                 fline("R1", "svc-report", "MED", "s.py:1", "far away"),
                 fline("R0", "svc-order", "LOW", "o.py:1", "its own"),
                 fline("R0", "agg-order", "LOW", "a.py:2", "already closed", mark="x")]
        self.put("pre-release.md", "# Pre-release\n\n" + "".join(t for t, _ in lines))
        md = self.run_tool("pack", self.feat, "svc-order", expect=0)
        for s in ("owner of b-order", "fellow consumer of b-order", "scoped to the boundary", "its own",
                  "\n1 other open findings in the feature (not relevant to this block)"):
            self.assertIn(s, md)
        for s in ("far away", "already closed"):
            self.assertNotIn(s, md)
        md = self.run_tool("pack", self.feat, "svc-report", expect=0)
        self.assertIn("- line 6: R1 · svc-report", md)
        self.assertIn("fellow consumer of b-order", md)                     # rm-orders owns b-rm
        self.assertIn("\n3 other open findings in the feature", md)
        h = lines[0][1]
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-1", "--lines", "3:" + h, expect=0)
        md = self.run_tool("pack", self.feat, "pre-R0-1", expect=0)
        self.assertNotIn("## Open findings", md)                             # a group packs its own lines
        self.assertNotIn("other open findings", md)
        self.assertIn("owner of b-order", md)

    # -- review fixes --------------------------------------------------------------------------------
    def test_progress_refuses_a_dirty_worktree_and_a_dirty_tree_is_not_fresh(self):
        wt = self.doing("agg-order")
        self.put("src/loose.txt", "not committed\n", base=wt)
        out = self.record("agg-order", expect=1)
        self.assertTrue(any("commit everything before a checkpoint" in p for p in out["problems"]))
        os.remove(os.path.join(wt, "src", "loose.txt"))
        self.record("agg-order")
        self.assertTrue(self.status()["resume"][0]["progress"]["fresh"])
        self.put("src/loose.txt", "after the checkpoint\n", base=wt)       # a crash after it: unverified
        self.assertFalse(self.status()["resume"][0]["progress"]["fresh"])
        self.assertNotIn("## Checkpoint", self.run_tool("pack", self.feat, "agg-order", expect=0))

    def test_progress_refuses_no_progress_and_non_blocks(self):
        wt = self.doing("agg-order")
        self.record("agg-order")
        out = self.record("agg-order", expect=1)
        self.assertIn("no progress since attempt 1: same head, same done list", out["problems"])
        self.record("agg-order", {"done": ["INV-1 green", "rejection"], "next": "n"})   # more done: progress
        self.commit(wt, "src/x.txt", "x\n")
        self.assertEqual(self.record("agg-order", {"done": ["INV-1 green", "rejection"], "next": "n"})["attempt"], 3)
        out = self.record("pre-R0-1", h="0" * 64, expect=1)
        self.assertIn("checkpoints are for manifest blocks only", out["problems"][0])

    def test_progress_extras_are_stored_and_packed_once(self):
        self.doing("agg-order")
        rw = self.put("rework/agg-order-1.md", "- fix the rounding\n")
        doc = self.put("dev-arch.md", "layout memory\n", base=self.tmp)
        out = self.run_tool("progress", "record", self.feat, "agg-order", "--head", "block/agg-order", "--spec-hash",
                            self.spec_hash("agg-order"), "--json", '{"done": [], "next": "n"}',
                            "--extra", os.path.join(self.tmp, "ghost.md"), expect=1)
        self.assertIn("--extra %s not found" % os.path.join(self.tmp, "ghost.md"), out["problems"])
        self.run_tool("progress", "record", self.feat, "agg-order", "--head", "block/agg-order", "--spec-hash",
                      self.spec_hash("agg-order"), "--json", '{"done": [], "next": "n"}', "--extra", rw,
                      "--extra", doc, expect=0)
        self.assertEqual(json.loads(mismagent.read(os.path.join(self.feat, "progress", "agg-order.json")))["extras"],
                         [rw, doc])
        md = self.run_tool("pack", self.feat, "agg-order", expect=0)
        self.assertIn("fix the rounding", md)
        self.assertIn("## Extra — dev-arch.md", md)
        md = self.run_tool("pack", self.feat, "agg-order", "--extra", doc, expect=0)
        self.assertEqual(md.count("## Extra — dev-arch.md"), 1)

    def chain(self, report_after):
        m = self.comp().replace("    commands: [BuildReport]\n", "    commands: [BuildReport]\n    composition: true\n"
                                "    after: [%s]\n" % report_after)
        self.put("architecture.md", ARCH, base=self.out)
        self.write_feature(m)

    def test_composition_chain_and_the_composition_diet(self):
        self.chain("rm-orders")
        self.assertIn(("composition.chain", "svc-report"), self.gaps()[0])
        self.assertIn("composition.chain", mismagent.TERMINAL_LINT)
        self.chain("rm-orders, svc-order")
        self.run_tool("lint", self.feat, expect=0)
        self.put("pre-release.md", "# Pre-release\n\n" + fline("R0", "svc-order", "MED", "m.py:1", "root debt")[0] +
                 fline("R0", "agg-order", "MED", "a.py:1", "unrelated")[0])
        md = self.run_tool("pack", self.feat, "svc-report", expect=0)
        self.assertIn("root debt", md)                                      # the earlier composition's line
        self.assertNotIn("unrelated", md)

    def test_an_empty_or_heading_root_line_is_no_root(self):
        self.write_feature(self.comp())
        for text in ("# A\n\ncomposition_root:\n## Next\n", "## composition_root: src/app\n",
                     "- composition_root: `` \n"):
            self.put("architecture.md", text, base=self.out)
            self.assertIn(("composition.root", "architecture.md"), self.gaps()[0], text)
        self.put("architecture.md", "- **composition_root:** `src/app/main`\n", base=self.out)
        self.run_tool("lint", self.feat, expect=0)

    def test_composition_roots_are_resolved_per_side(self):
        self.write_feature(self.comp("    composition: true\n    after: [agg-order]\n    side: app\n"))
        self.put("architecture.md", "# A\n\n```yaml\ncomposition_roots:\n  admin: src/admin\n```\n", base=self.out)
        self.assertIn(("composition.root", "architecture.md"), self.gaps()[0])        # none for side app
        self.put("architecture.md", "# A\n\n- `composition_root: legacy/one`\n\n```yaml\ncomposition_roots:\n"
                 "  admin: src/admin\n  app: src/app\n```\n", base=self.out)
        self.run_tool("lint", self.feat, expect=0)
        self.assertEqual(mismagent.composition_root(mismagent.Feature(self.feat), "app"), "src/app")  # map wins
        self.put("architecture.md", "# A\n\n```yaml\ncomposition_roots:\n  app: null\n```\n", base=self.out)
        self.assertIn(("composition.root", "architecture.md"), self.gaps()[0])        # a null root is none
        self.put("architecture.md", "- `composition_root: one/root`\n", base=self.out)
        self.put("profile.md", "```yaml\nsides:\n  app: {path: a}\n  admin: {path: b}\n```\n", base=self.out)
        self.assertIn(("composition.root", "architecture.md"), self.gaps()[0])        # one line, two sides

    def test_code_paths_name_existing_code_and_leave_other_blocks_specs_alone(self):
        before = {b: self.spec_hash(b) for b in ("agg-order", "svc-order")}
        self.put("src/orders/api.py", "x\n", base=self.repo)
        self.put("src/local-only.py", "x\n", base=self.repo)                             # never committed
        sh(self.repo, "git", "add", "src/orders/api.py")
        sh(self.repo, "git", "commit", "-q", "-m", "api")
        m = MANIFEST.replace("    view_shape: { orderId: string, total: int }\n",
                             "    view_shape: { orderId: string, total: int }\n    code_paths: [src/orders/api.py, src/gone.py]\n", 1)
        self.write_feature(m)
        self.assertIn(("code_paths.exist", "rm-orders"), self.gaps()[0])
        self.write_feature(m.replace(", src/gone.py", ", src/local-only.py"))
        self.assertIn(("code_paths.exist", "rm-orders"), self.gaps()[0])               # the committed tree counts
        self.write_feature(m.replace(", src/gone.py", ""))
        self.assertNotIn(("code_paths.exist", "rm-orders"), self.gaps()[0])
        self.write_feature(m.replace("[src/orders/api.py, src/gone.py]", "src/orders/api.py"))
        self.assertIn(("code_paths.shape", "rm-orders"), self.gaps()[0])
        self.write_feature(m.replace("    code_paths: [", "    after: [agg-order]\n    code_paths: [", 1))
        self.assertNotIn(("code_paths.exist", "rm-orders"), self.gaps()[0])            # agg-order owes that code yet
        self.assertEqual({b: self.spec_hash(b) for b in before}, before)               # only its own row changed
        self.write_feature(m.replace("[src/orders/api.py, src/gone.py]", "[/abs/path]"))
        self.assertIn("code_paths", json.dumps(self.run_tool("manifest", "render", self.feat)))

    def test_the_pack_names_the_code_to_change_and_the_entry_files_to_read(self):
        self.put("src/orders/api.py", "x\n", base=self.repo)
        self.write_feature(MANIFEST.replace("    commands: [PlaceOrder]\n", "    commands: [PlaceOrder]\n"
                                            "    code_paths: [src/orders/api.py]\n", 1))
        self.put("architecture.md", "# A\n\n```yaml\nmodules:\n  - id: orders\n    root: src/orders\n"
                 "    entry_files: [src/orders/api.py, src/orders/ports.py]\n  - id: reports\n    root: src/reports\n"
                 "    entry_files: [src/reports/api.py]\n```\n", base=self.out)
        md = self.run_tool("pack", self.feat, "svc-order", expect=0)
        sec = md[md.index("## Existing code"):]
        self.assertIn("To change (`code_paths`):\n- `src/orders/api.py`", sec)
        self.assertIn("- `src/orders/ports.py`", sec)                                    # its context's entry
        self.assertNotIn("src/reports", sec.split("## ")[1])                             # not its dependency

    def test_codemap_groups_by_module_marks_entry_files_and_skips_the_output_dir(self):
        for f in ("src/orders/api.py", "src/orders/impl/x.py", "src/reports/r.py", "tools/t.sh"):
            self.put(f, "x\n", base=self.repo)
        self.put("profile.md", "# P\n\n```yaml\nsides:\n  app:\n    path: src\n```\n", base=self.out)
        sh(self.repo, "git", "add", ".")
        sh(self.repo, "git", "commit", "-q", "-m", "code")
        md = self.run_tool("codemap", self.out, "--ref", "main", "--files", expect=0)
        self.assertIn("modules unknown", md)
        self.assertIn("- **orders** `src/orders` — 2 files", md)
        self.assertNotIn(".mismagent", md)
        self.assertNotIn("tools/t.sh", md)                                              # outside the side
        self.put("architecture.md", "# A\n\n```yaml\nmodules:\n  - id: ord\n    side: app\n    root: src/orders\n"
                 "    entry_files: [src/orders/api.py]\n```\n", base=self.out)
        self.put("profile.md", "# P\n\n```yaml\nsides:\n  app:\n    path: src\n  ops:\n    path: tools\n```\n",
                 base=self.out)
        md = self.run_tool("codemap", self.out, "--ref", "main", "--side", "ops", "--files", expect=0)
        self.assertIn("(outside any module) — 1 files: `tools/t.sh`", md)             # ops: its own fallback
        md = self.run_tool("codemap", self.out, "--ref", "main", "--files", "--module", "ord", expect=0)
        self.assertIn("  - * `src/orders/api.py`", md)
        self.assertIn("  - `src/orders/impl/x.py`", md)
        self.assertNotIn("src/reports", md)


def finding(sev, at, issue, fix="Defer", evidence="seen in the diff"):
    return {"sev": sev, "at": at, "issue": issue, "fix": fix, "evidence": evidence}


class TestV025(Base):
    """v0.25: `review ingest` (reports → one action) and `state commit` (the bookkeeping, exactly)."""

    def setUp(self):
        super().setUp()
        self.wt = self.block_wt("svc-order")
        self.tip = self.commit(self.wt, "src/svc.txt", "svc\n")
        self.rdir = os.path.join(self.tmp, "reviews")

    def report(self, reviewer, verdict, findings=(), failures=(), attempt=1, bid="svc-order", **over):
        r = dict(version=1, id=bid, attempt=attempt, reviewer=reviewer, sha=self.tip,
                 spec_hash=self.spec_hash(bid), verdict=verdict, checks=["gate green"], failures=list(failures),
                 findings=list(findings), notes="")
        r.update(over)
        path = os.path.join(self.rdir, "%s-%d-%s.json" % (bid, attempt, reviewer))
        os.makedirs(self.rdir, exist_ok=True)
        with open(path, "w") as f:
            json.dump(r, f)
        return path

    def ingest(self, *files, bid="svc-order", depth="standard", attempt=1, sha=None, h=None, expect=0):
        args = ["review", "ingest", self.feat, bid, "--attempt", str(attempt), "--depth", depth,
                "--sha", sha or self.tip, "--spec-hash", h or self.spec_hash(bid)]
        for f in files:
            args += ["--file", f]
        return self.run_tool(*args, expect=expect)

    def pre(self):
        p = os.path.join(self.feat, "pre-release.md")
        return [l for l in mismagent.read(p).splitlines() if l.startswith("- [")] if os.path.isfile(p) else []

    # -- review ingest -------------------------------------------------------------------------------
    def test_standard_pass_promotes_records_the_proof_and_files_deferrals_once(self):
        f = self.report("verifier", "PASS", [finding("MED", "src/svc.txt:1", "naming · unclear"),
                                             finding("LOW", "src/svc.txt#Svc.run", "a comment")])
        out = self.ingest(f)
        self.assertEqual((out["ok"], out["action"], out["rework"], out["proof"], out["appended"]),
                         (True, "promote", None, True, 2))
        self.assertEqual(out["counts"], {"HIGH": 0, "MED": 1, "LOW": 1, "failures": 0})
        self.assertTrue(self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", self.tip,
                                      expect=0)["fresh"])
        lines = self.pre()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("- [ ] R0 · svc-order · MED · src/svc.txt:1 · naming - unclear · verifier · "))
        self.run_tool("lint", self.feat, expect=0)                                  # well-formed seven-field lines
        again = self.ingest(f)                                                       # an identical retry
        self.assertEqual(again, dict(out, repeat=True))                              # the recorded result
        self.assertEqual(self.pre(), lines)
        f2 = self.report("verifier", "PASS", [finding("MED", "src/svc.txt:1", "naming · unclear")], attempt=2)
        self.assertEqual(self.ingest(f2, attempt=2)["appended"], 0)                  # a finding is filed once
        self.assertEqual(self.pre(), lines)
        self.compose("start", "svc-order", expect=0)                                 # the proof is the real one

    def test_deep_needs_both_reports_and_everything_must_match(self):
        v = self.report("verifier", "PASS", [finding("MED", "a.py:1", "x")])
        out = self.ingest(v, depth="deep", expect=1)
        self.assertEqual(out["refused"], "nothing written")
        self.assertIn("depth deep requires a code-review report", out["problems"])
        self.assertEqual(self.pre(), [])
        self.assertFalse(os.path.exists(os.path.join(self.feat, "review-proof", "svc-order.json")))
        self.assertIn("depth standard takes no code-review report",
                      self.ingest(v, self.report("code-review", "APPROVE"), expect=1)["problems"])
        parent = sh(self.wt, "git", "rev-parse", "HEAD~1")
        self.assertIn("not the tip of block/svc-order", self.ingest(v, sha=parent, expect=1)["problems"][0])
        self.assertIn("not the current spec hash", self.ingest(v, h="0" * 64, expect=1)["problems"][0])
        bad = self.report("verifier", "PASS", sha=parent)
        self.assertIn("is not --sha", " ".join(self.ingest(bad, expect=1)["problems"]))
        bad = self.report("verifier", "PASS", attempt=2)
        self.assertIn("attempt 2, not 1", " ".join(self.ingest(bad, expect=1)["problems"]))
        bad = self.report("verifier", "APPROVE", findings=[{"sev": "MED", "at": "a.py", "issue": "x"}])
        probs = " ".join(self.ingest(bad, expect=1)["problems"])
        self.assertIn("verdict 'APPROVE'", probs)
        self.assertIn("keys must be exactly", probs)
        self.assertEqual(self.pre(), [])
        v = self.report("verifier", "PASS", [finding("MED", "a.py:1", "x")])        # the bad ones overwrote it
        c = self.report("code-review", "APPROVE", [finding("LOW", "b.py:2", "y")])
        out = self.ingest(v, c, depth="deep")
        self.assertEqual((out["action"], out["appended"]), ("promote", 2))
        self.assertTrue(self.pre()[1].endswith(" · code-review · " + self.pre()[1].split(" · ")[-1]))

    def test_fail_writes_one_rework_file_per_cycle_then_parks_at_the_cap(self):
        v = self.report("verifier", "FAIL", [finding("HIGH", "src/svc.txt:1", "total can go negative", "Patch"),
                                             finding("MED", "src/svc.txt:2", "dup")], failures=["AC2 red"])
        out = self.ingest(v)
        self.assertEqual((out["action"], out["proof"], out["appended"]), ("rework", False, 1))
        self.assertEqual(out["rework"], os.path.join(self.feat, "rework", "svc-order-1.md"))
        text = mismagent.read(out["rework"])
        for s in ("AC2 red", "total can go negative", "## HIGH findings"):
            self.assertIn(s, text)
        self.assertNotIn("dup", text)                                                # a Defer stays in pre-release
        self.assertEqual(self.ingest(v)["rework"], out["rework"])                    # same attempt: same file
        other = self.report("verifier", "FAIL", failures=["another"])                # same attempt, other report
        self.assertIn("already ingested", self.ingest(other, expect=1)["problems"][0])
        self.assertEqual(len(self.pre()), 1)
        self.assertFalse(os.path.exists(os.path.join(self.feat, "review-proof", "svc-order.json")))
        self.tip = self.commit(self.wt, "src/svc.txt", "svc 2\n")
        c = self.report("code-review", "CHANGES", [finding("HIGH", "src/svc.txt:1", "still", "Patch")], attempt=2)
        v2 = self.report("verifier", "PASS", attempt=2)
        out = self.ingest(v2, c, depth="deep", attempt=2)
        self.assertEqual((out["action"], os.path.basename(out["rework"])), ("rework", "svc-order-2.md"))
        self.tip = self.commit(self.wt, "src/svc.txt", "svc 3\n")
        out = self.ingest(self.report("verifier", "FAIL", failures=["AC2 red"], attempt=3), attempt=3)
        self.assertEqual((out["action"], out["rework"]), ("park", None))
        self.assertIn("rework cap", out["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.feat, "rework", "svc-order-3.md")))
        ev = self.put("red.txt", "contract test b-order red\n", base=self.tmp)
        out = self.run_tool("rework", "write", self.feat, "svc-order", "--reason", "candidate-red", "--evidence", ev,
                            expect=0)
        self.assertEqual((out["ok"], out["action"], out["rework"]), (True, "park", None))   # the same cap

    def test_rework_write_numbers_like_ingest_and_drops_the_proof(self):
        self.ingest(self.report("verifier", "PASS"))
        ev = self.put("red.txt", "gate red: 2 failing tests\n", base=self.tmp)
        out = self.run_tool("rework", "write", self.feat, "svc-order", "--reason", "candidate-red", "--evidence", ev,
                            expect=0)
        self.assertEqual((out["action"], os.path.basename(out["rework"])), ("rework", "svc-order-1.md"))
        self.assertIn("gate red: 2 failing tests", mismagent.read(out["rework"]))
        self.assertIn("candidate-red", mismagent.read(out["rework"]))
        self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", self.tip, expect=1)
        self.compose("start", "svc-order", expect=1)
        out = self.ingest(self.report("verifier", "FAIL", failures=["x"], attempt=2), attempt=2)
        self.assertEqual(os.path.basename(out["rework"]), "svc-order-2.md")
        self.run_tool("rework", "write", self.feat, "svc-order", "--reason", "merge-conflict", "--evidence",
                      os.path.join(self.tmp, "none.txt"), expect=1)
        self.run_tool("rework", "write", self.feat, "nope", "--reason", "other", "--evidence", ev, expect=1)

    def test_a_non_promote_outcome_invalidates_the_review_proof(self):
        cases = [("FAIL", self.report, dict(failures=["AC1 red"]), "rework"),
                 ("PASS", self.report, dict(findings=[finding("LOW", "a.py:1", "which?", "Decision")]), "decide"),
                 ("SKIP", self.report, dict(failures=["no runner"]), "blocked")]
        n = 0
        for verdict, rep_, kw, action in cases:
            n += 1
            out = self.ingest(rep_("verifier", "PASS", attempt=n), attempt=n)
            self.assertEqual(out["action"], "promote")
            self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", self.tip, expect=0)
            n += 1
            out = self.ingest(rep_("verifier", verdict, attempt=n, **kw), attempt=n)
            self.assertEqual((out["action"], out["proof_dropped"]), (action, True), verdict)
            self.run_tool("proof", "check", self.feat, "review", "svc-order", "--sha", self.tip, expect=1)
            self.compose("start", "svc-order", expect=1)

    def test_malformed_types_are_refused_never_a_crash(self):
        for over in (dict(reviewer=["verifier"]), dict(reviewer=None), dict(verdict=["PASS"]), dict(attempt="1"),
                     dict(version="1"), dict(failures="x"), dict(failures=[1]), dict(findings="x"),
                     dict(findings=[{"sev": 1, "at": "a:1", "issue": "i", "fix": "Defer", "evidence": ""}]),
                     dict(findings=[{"sev": "LOW", "at": "a:1", "issue": "i", "fix": "Defer", "evidence": None}]),
                     dict(id=3), dict(sha=None), dict(objections="x"), dict(objections=[{"about": "D-0001"}]),
                     dict(findings=[{"sev": "LOW", "at": "a.py:127,142", "issue": "i", "fix": "Defer", "evidence": ""}])):
            path = self.report("verifier", "PASS")
            with open(path) as f:
                r = dict(json.load(f), **over)
            with open(path, "w") as f:
                json.dump(r, f)
            out = self.ingest(path, expect=1)
            self.assertEqual(out["refused"], "nothing written", over)
        path = os.path.join(self.rdir, "list.json")
        with open(path, "w") as f:
            f.write("[1, 2]")
        self.assertIn("not a JSON object", self.ingest(path, expect=1)["problems"][0])

    def test_objections_are_returned_compact(self):
        f = self.report("verifier", "PASS", objections=[{"about": "D-0003", "text": "the cache  key\nignores the tenant"}])
        out = self.ingest(f)
        self.assertEqual(out["objections"], [{"reviewer": "verifier", "about": "D-0003",
                                              "text": "the cache key ignores the tenant"}])

    def test_decision_decides_first_and_skip_is_blocked(self):
        out = self.ingest(self.report("verifier", "PASS", [finding("MED", "a.py:1", "which rounding?", "Decision")]))
        self.assertEqual((out["action"], out["proof"], out["appended"]), ("decide", False, 0))
        self.assertIn("which rounding?", out["reason"])
        out = self.ingest(self.report("verifier", "PASS", attempt=2), self.report("code-review", "BLOCKED", attempt=2),
                          depth="deep", attempt=2)
        self.assertEqual(out["action"], "decide")
        out = self.ingest(self.report("verifier", "SKIP", failures=["the gate cannot run here"], attempt=3), attempt=3)
        self.assertEqual((out["action"], out["rework"]), ("blocked", None))
        self.assertIn("the gate cannot run here", out["reason"])
        out = self.ingest(self.report("verifier", "SKIP", [finding("HIGH", "a.py:1", "which store?", "Decision")],
                                      failures=["no runner"], attempt=4), attempt=4)
        self.assertEqual(out["action"], "decide")                                    # a Decision comes first
        self.assertEqual(glob.glob(os.path.join(self.feat, "rework", "*")), [])

    def group(self):
        self.put("rework/pre-R0-1-1.md", "---\nrelease: R0\nblocks: [agg-order, svc-order]\nfindings: [abcdefabcdef]"
                 "\n---\n- [ ] R0 · agg-order · MED · src/a.txt:1 · naming · verifier · 2026-09-24\n"
                 "- [ ] R0 · svc-order · MED · src/svc.txt:3 · naming · verifier · 2026-09-24\n")
        wt = self.block_wt("pre-R0-1")
        self.tip = self.commit(wt, "src/g.txt", "g\n")
        return wt

    def test_a_release_group_id_is_ingested_on_its_branch_and_retried_identically(self):
        wt = self.group()
        f = self.report("verifier", "FAIL", [finding("HIGH", "src/g.txt:1", "broken", "Patch"),
                                             finding("LOW", "src/svc.txt:9", "style"),
                                             finding("LOW", "src/other.txt:1", "wording")], bid="pre-R0-1")
        out = self.ingest(f, bid="pre-R0-1")
        self.assertEqual((out["action"], os.path.basename(out["rework"])), ("rework", "pre-R0-1-2.md"))
        self.assertIn("cycle 1 of 2", out["reason"])                                 # -1 is the group's spec
        pre = self.pre()
        self.assertTrue(pre[0].startswith("- [ ] R0 · svc-order · LOW · src/svc.txt:9 · [pre-R0-1] style · verifier"))
        self.assertTrue(pre[1].startswith("- [ ] R0 · agg-order · LOW · src/other.txt:1 · [pre-R0-1] wording"))
        again = self.ingest(f, bid="pre-R0-1", h="0" * 64)                          # the spec moved with its rework file
        self.assertEqual(again, dict(out, repeat=True))
        self.assertEqual(self.pre(), pre)
        self.assertEqual(len(glob.glob(os.path.join(self.feat, "rework", "pre-R0-1-*.md"))), 2)
        stale = self.report("verifier", "PASS", bid="pre-R0-1", attempt=2, spec_hash="0" * 64)
        self.assertIn("not the current spec hash", self.ingest(stale, bid="pre-R0-1", attempt=2, h="0" * 64,
                                                               expect=1)["problems"][0])
        self.tip = self.commit(wt, "src/g.txt", "g2\n")
        out = self.ingest(self.report("verifier", "PASS", bid="pre-R0-1", attempt=2), bid="pre-R0-1", attempt=2)
        self.assertEqual((out["action"], out["proof"]), ("promote", True))
        self.review("pre-R0-1", h=self.spec_hash("pre-R0-1"))                        # same proof path as `proof record`
        h = self.findings_of_release()
        self.run_tool("release", "group", self.feat, "R0", "--id", "pre-R0-2", "--lines", h, expect=0)

    def findings_of_release(self):
        f = [x for x in mismagent.parse_findings(mismagent.Feature(self.feat)) if "[pre-R0-1] style" in x["text"]][0]
        return "%d:%s" % (f["line"], f["finding"])

    def test_a_release_group_parks_after_two_rework_cycles(self):
        wt = self.group()
        for n in (1, 2):
            out = self.ingest(self.report("verifier", "FAIL", failures=["red %d" % n], bid="pre-R0-1", attempt=n),
                              bid="pre-R0-1", attempt=n)
            self.assertEqual(os.path.basename(out["rework"]), "pre-R0-1-%d.md" % (n + 1))
            self.tip = self.commit(wt, "src/g.txt", "g%d\n" % n)
        out = self.ingest(self.report("verifier", "FAIL", failures=["red 3"], bid="pre-R0-1", attempt=3),
                          bid="pre-R0-1", attempt=3)
        self.assertEqual((out["action"], out["rework"]), ("park", None))
        ev = self.put("red.txt", "red\n", base=self.tmp)
        out = self.run_tool("rework", "write", self.feat, "pre-R0-1", "--reason", "candidate-red", "--evidence", ev,
                            expect=0)
        self.assertEqual(out["action"], "park")

    # -- state commit --------------------------------------------------------------------------------
    def state(self, expect, msg="state"):
        return self.run_tool("state", "commit", self.feat, "-m", msg, "--integration", "feature/shop", expect=expect)

    def test_state_commit_only_the_output_dir_on_the_integration_checkout(self):
        self.assertIn("not feature/shop", self.state(1)["refused"])                  # the checkout is on main
        sh(self.repo, "git", "checkout", "-q", "feature/shop")
        self.assertEqual(self.state(0), {"ok": True, "committed": False})
        self.put("gone.md", "x\n")
        sh(self.repo, "git", "add", ".mismagent")
        sh(self.repo, "git", "commit", "-q", "-m", "gone")
        os.remove(os.path.join(self.feat, "gone.md"))
        self.put("rework/svc-order-1.md", "new\n")
        self.put("README", "changed\n", base=self.repo)
        sh(self.repo, "git", "add", "README")
        out = self.state(1)
        self.assertEqual(out["outside"], ["README"])
        sh(self.repo, "git", "reset", "-q", "README")                                # unstaged: left alone
        out = self.state(0, "bookkeeping")
        self.assertTrue(out["committed"])
        self.assertEqual(sorted(out["paths"]), [".mismagent/features/shop/gone.md",
                                                ".mismagent/features/shop/rework/svc-order-1.md"])
        self.assertEqual(sh(self.repo, "git", "log", "-1", "--format=%s"), "bookkeeping")
        self.assertEqual(sh(self.repo, "git", "rev-parse", "feature/shop"), out["sha"])
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain"), "M README")
        self.assertEqual(self.state(0), {"ok": True, "committed": False})


class TestV0252(Base):
    """v0.25.2: open questions close, report templates, lenient `at`/objections, --answered, why rules."""
    report, ingest, pre = TestV025.report, TestV025.ingest, TestV025.pre

    def setUp(self):
        Base.setUp(self)
        self.wt = self.block_wt("svc-order")
        self.tip = self.commit(self.wt, "src/svc.txt", "svc\n")
        self.rdir = os.path.join(self.tmp, "reviews")

    def notes(self, *ids):
        return self.put("decisions.md", "# Decision notes — shop\n\n" + "\n".join(note(i) for i in ids))

    # -- 1 · open questions close --------------------------------------------------------------------
    def test_a_question_closes_on_a_recorded_decision_and_stops_waiting_or_parking(self):
        for q in ("ui-turno", "catalogo-categorie-cmd", "scaffold-app"):
            self.put("open-questions/%s.md" % q, "# Open question — %s\n\n## Decision — user\n- chosen: A\n" % q)
        status = lambda: self.run_tool("status", self.feat, "--integration", "feature/shop")["waiting"]
        self.assertIn("open question: open-questions/ui-turno.md", status())
        self.assertIn({"id": "scaffold-app", "reason": "parked: open-questions/scaffold-app.md"},
                      self.run_tool("ready", self.feat)["excluded"])
        close = lambda q, d, expect: self.run_tool("question", "close", self.feat, q, "--decision", d, expect=expect)
        self.assertIn("record the answer first", close("ui-turno", "D-0023", 1)["refused"])   # no decisions.md
        self.notes("D-0020", "D-0023")
        self.assertIn("not an entry", close("ui-turno", "D-0099", 1)["refused"])
        self.assertIn("no open question", close("nope", "D-0020", 1)["refused"])
        sh(self.repo, "git", "add", ".")
        sh(self.repo, "git", "commit", "-q", "-m", "questions")
        out = close("ui-turno", "D-0023", 0)
        self.assertEqual((out["path"], out["git"]), (os.path.join(self.feat, "open-questions", "closed", "ui-turno.md"),
                                                    True))
        self.assertRegex(mismagent.read(out["path"]), r"chosen: A\n\nClosed by D-0023 on \d{4}-\d{2}-\d{2}\n$")
        self.assertFalse(os.path.exists(os.path.join(self.feat, "open-questions", "ui-turno.md")))
        self.assertEqual(close("catalogo-categorie-cmd", "D-0020", 0)["git"], True)
        close("scaffold-app", "D-0020", 0)
        self.assertFalse([w for w in status() if w.startswith("open question")])
        self.assertIn("scaffold-app", [r["id"] for r in self.run_tool("ready", self.feat)["ready"]])
        self.assertIn("no open question", close("ui-turno", "D-0023", 1)["refused"])      # closed once
        self.put("open-questions/ui-turno.md", "parked again\n")
        self.assertTrue(close("ui-turno", "D-0023", 0)["path"].endswith("closed/ui-turno-2.md"))

    # -- 2 · report templates and lenient ingest -----------------------------------------------------
    def template(self, reviewer, *extra, expect=0, attempt=1):
        return self.run_tool("review", "template", self.feat, "svc-order", "--attempt", str(attempt), "--reviewer",
                             reviewer, "--sha", self.tip, "--spec-hash", self.spec_hash("svc-order"), *extra,
                             expect=expect)

    def test_a_filled_template_ingests_on_the_first_attempt_an_unfilled_one_never(self):
        t = self.template("code-review")
        self.assertEqual(set(t), set(mismagent.REPORT_KEYS + mismagent.REPORT_OPTIONAL))
        self.assertEqual((t["id"], t["attempt"], t["sha"], t["reviewer"]), ("svc-order", 1, self.tip, "code-review"))
        self.assertIn("never a list", t["findings"][0]["at"])
        self.assertIn("at most 40 words", t["objections"][0]["text"])
        path = os.path.join(self.rdir, "svc-order-1-verifier.json")
        self.assertEqual(self.template("verifier", "--out", path)["file"], path)
        self.assertEqual(self.ingest(path, expect=1)["refused"], "nothing written")    # placeholders refused
        with open(path) as f:
            r = json.load(f)
        r.update(verdict="PASS", failures=[], notes="")
        r["findings"][0].update(sev="LOW", at="src/svc.txt", issue="naming", fix="Defer")
        r["objections"][0].update(about="D-0003", text="w " * 45)
        with open(path, "w") as f:
            json.dump(r, f)
        out = self.ingest(path)
        self.assertEqual((out["action"], out["appended"]), ("promote", 1))
        self.assertEqual(out["warnings"], ["svc-order-1-verifier.json objection 0: 45 words, truncated to 40"])
        self.assertEqual(len(out["objections"][0]["text"].split()), 40)
        self.assertIn(" · LOW · src/svc.txt · naming · ", self.pre()[0])                # a path alone is a locator
        self.run_tool("lint", self.feat, expect=0)
        self.template("verifier", "--spec-hash", "0" * 64, expect=1)                     # last --spec-hash wins
        self.run_tool("review", "template", self.feat, "svc-order", "--attempt", "1", "--sha", self.tip,
                      "--spec-hash", self.spec_hash("svc-order"), expect=2)             # no --reviewer

    # -- 3 · an answered decision promotes without a new review --------------------------------------
    def test_answered_decide_promotes_the_same_attempt(self):
        f = self.report("verifier", "PASS", [finding("MED", "src/svc.txt:1", "loosen rule 5?", "Decision")])
        self.assertEqual(self.ingest(f)["action"], "decide")
        ans = lambda *d, expect=0: self.run_tool("review", "ingest", self.feat, "svc-order", "--attempt", "1", "--depth",
                                                 "standard", "--file", f, "--sha", self.tip, "--spec-hash",
                                                 self.spec_hash("svc-order"), *[x for i in d for x in ("--answered", i)],
                                                 expect=expect)
        self.assertIn("no such entry", ans("D-0023", expect=1)["problems"][0])          # record it first
        self.notes("D-0022", "D-0023")
        out = ans("D-0023", "D-0022")
        self.assertEqual((out["action"], out["proof"], out["answered"]), ("promote", True, ["D-0022", "D-0023"]))
        self.assertIn("answered by D-0022, D-0023", out["reason"])
        self.assertEqual(ans("D-0022", "D-0023"), dict(out, repeat=True))                # recorded with its answers
        self.assertIn("already ingested", ans("D-0022", expect=1)["problems"][0])        # promote is final
        self.assertIn("already ingested", self.ingest(f, expect=1)["problems"][0])      # answers dropped: refused
        self.compose("start", "svc-order", expect=0)
        mark = mismagent.load_json(os.path.join(self.feat, "review-ingest", "svc-order-1.json"))
        self.assertEqual(mark["answered"], ["D-0022", "D-0023"])

    def test_answered_needs_a_decision_and_leaves_other_failures(self):
        self.notes("D-0023")
        p = self.report("verifier", "PASS")
        out = self.run_tool("review", "ingest", self.feat, "svc-order", "--attempt", "1", "--depth", "standard",
                            "--file", p, "--sha", self.tip, "--spec-hash", self.spec_hash("svc-order"),
                            "--answered", "D-0023", expect=1)
        self.assertIn("no Decision finding", out["problems"][0])
        self.assertEqual(self.pre(), [])
        p = self.report("verifier", "FAIL", [finding("HIGH", "a.py:1", "which store?", "Decision")],
                        failures=["AC2 red"], attempt=2)
        out = self.run_tool("review", "ingest", self.feat, "svc-order", "--attempt", "2", "--depth", "standard",
                            "--file", p, "--sha", self.tip, "--spec-hash", self.spec_hash("svc-order"),
                            "--answered", "D-0023", expect=0)
        self.assertEqual(out["action"], "rework")                                      # the failure still counts

    # -- 4 · why rules discoverable --------------------------------------------------------------------
    def test_why_help_states_the_rules_and_the_template_appends(self):
        p = subprocess.run([sys.executable, TOOL, "why", "append", "--help"], capture_output=True, text=True)
        for s in ("ONE", "physical line", "ALL THREE", "Revisit 20", "highest id + 1", "≤ 220"):
            self.assertIn(s, p.stdout)
        path = self.notes("D-0001", "D-0004")
        tpl = subprocess.run([sys.executable, TOOL, "why", "template", path], capture_output=True, text=True).stdout
        self.assertTrue(tpl.startswith("### D-0005 · "))
        entry = self.put("entry.md", tpl, base=self.tmp)
        self.assertEqual(self.run_tool("why", "append", path, "--entry", entry, expect=0)["appended"], ["D-0005"])
        self.run_tool("why", "check", expect=2)


class TestPromptInvocations(unittest.TestCase):
    """Every `MM …` / `mismagent.py …` invocation written in the plugin's Markdown must parse."""

    def invocations(self):
        for path in glob.glob(os.path.join(PLUGIN, "**", "*.md"), recursive=True):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            spans = re.findall(r"^```[^\n]*\n(.*?)^```", text, re.S | re.M)
            text = re.sub(r"^```[^\n]*\n.*?^```", "", text, flags=re.S | re.M)
            lines = [l for s in spans for l in s.splitlines()] + re.findall(r"`([^`]+)`", text)
            for span in lines:
                m = re.search(r"(?:^MM|mismagent\.py\"?)\s+(.*)$", " ".join(span.split()))
                if m:
                    yield os.path.relpath(path, PLUGIN), span, m.group(1)

    @staticmethod
    def argv(rest):
        """Placeholders → dummies: `<a|b>` → a, `<…>` → x (`1` after an integer option such as
        `--attempt`), `record|check` → record, `[opt]` → opt, `GLOB…` → GLOB."""
        rest = re.sub(r"<([^>]*)>", lambda m: m.group(1).split("|")[0] if "|" in m.group(1) else "x", rest)
        out = []
        for tok in shlex.split(rest.replace("[", " ").replace("]", " ")):
            tok = tok.rstrip("…")
            if tok:
                out.append(tok.split("|")[0] if not tok.startswith("-") else tok)
        return [("1" if out[k - 1] in ("--attempt",) and not t.isdigit() else t) if k else t for k, t in enumerate(out)]

    def test_every_invocation_parses(self):
        parser, seen, bad = mismagent.build_parser(), 0, []
        for where, span, rest in self.invocations():
            try:
                argv = self.argv(rest)
            except ValueError as e:
                bad.append("%s: `%s` -> %s" % (where, span, e))
                continue
            if len(argv) <= (2 if argv and argv[0] in ("proof", "compose", "why", "manifest", "release", "progress", "review", "state", "rework", "question") else 1):
                continue  # a name reference (`MM status`), not an invocation
            if "--help" in argv or "-h" in argv:
                continue  # a pointer to a command's help, not an invocation
            seen += 1
            try:
                with open(os.devnull, "w") as null, redirect_stderr(null):
                    parser.parse_args(argv)
            except SystemExit:
                bad.append("%s: `%s` -> %s" % (where, span, argv))
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertGreater(seen, 10)


SHELLS = [sh_ for sh_ in ("bash", "zsh") if shutil.which(sh_)]
ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}|\$CLAUDE_PLUGIN_ROOT")


def run_in_shells(cmd, cwd):
    """[(shell, returncode, stderr)] — `cmd` run by each available shell, CLAUDE_PLUGIN_ROOT unset."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    return [(s_, p.returncode, p.stderr.strip()[-200:]) for s_ in SHELLS
            for p in [subprocess.run([s_, "-c", cmd], cwd=cwd, env=env, capture_output=True, text=True)]]


class TestExecutablePaths(unittest.TestCase):
    """The tool command a prompt writes must RUN, not only parse: Claude Code substitutes
    `${CLAUDE_PLUGIN_ROOT}` in loaded skill/agent/command content and exports nothing to Bash, so
    the command is taken from the prompt, substituted the documented way (the braced form only),
    and run with `--help` from an unrelated cwd, with no CLAUDE_PLUGIN_ROOT, in bash and zsh, from
    an install path holding spaces."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = os.path.realpath(tempfile.mkdtemp())
        cls.root = os.path.join(cls.tmp, "plugin cache", "mismagent")  # a path with spaces
        shutil.copytree(PLUGIN, cls.root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        cls.cwd = os.path.join(cls.tmp, "project", ".worktrees", "shop", "agg-order")
        os.makedirs(cls.cwd)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    @staticmethod
    def substitute(text, root):
        return text.replace("${CLAUDE_PLUGIN_ROOT}", root)  # the ONLY substitution Claude Code makes

    def commands(self):
        """{(file, command)} — every `python3 "<…CLAUDE_PLUGIN_ROOT…>.py"` written in a prompt."""
        out = set()
        for path in glob.glob(os.path.join(PLUGIN, "**", "*.md"), recursive=True):
            if "/tests/" in path:
                continue
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r"python3\s+(\"[^\"\n]*CLAUDE_PLUGIN_ROOT[^\"\n]*\"|[^\s`\"]*CLAUDE_PLUGIN_ROOT[^\s`\"]*)", text):
                out.add((os.path.relpath(path, PLUGIN), m.group(0)))
        return sorted(out)

    def test_the_old_braceless_form_fails(self):
        self.assertTrue(SHELLS)
        cmd = self.substitute('python3 "$CLAUDE_PLUGIN_ROOT/tools/mismagent.py" --help', self.root)
        self.assertTrue(all(rc != 0 for _, rc, _ in run_in_shells(cmd, self.cwd)))
        cmd = self.substitute('python3 "${CLAUDE_PLUGIN_ROOT}/tools/mismagent.py" --help', self.root)
        self.assertEqual([rc for _, rc, _ in run_in_shells(cmd, self.cwd)], [0] * len(SHELLS))

    def test_every_prompt_tool_command_runs(self):
        cmds, bad = self.commands(), []
        self.assertGreater(len(cmds), 5)
        for where, cmd in cmds:
            for shell, rc, err in run_in_shells(self.substitute(cmd, self.root) + " --help", self.cwd):
                if rc:
                    bad.append("%s [%s]: `%s` -> %s" % (where, shell, cmd, err))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_every_plugin_root_path_resolves_and_read_docs_carry_none(self):
        bad = []
        for path in glob.glob(os.path.join(PLUGIN, "**", "*.md"), recursive=True):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(path, PLUGIN)
            if rel in ("tools/CLI.md", "tools/LOOP.md"):  # read with Read: nothing substitutes there
                bad += ["%s: names CLAUDE_PLUGIN_ROOT" % rel] if "CLAUDE_PLUGIN_ROOT" in text else []
                continue
            bad += ["%s: `$CLAUDE_PLUGIN_ROOT` (no braces) is left to the shell, where it is unset" % rel
                    for _ in re.findall(r"\$CLAUDE_PLUGIN_ROOT", text)][:1]
            for p in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", text):
                if not os.path.exists(os.path.join(PLUGIN, p.rstrip("."))):
                    bad.append("%s: ${CLAUDE_PLUGIN_ROOT}/%s does not exist" % (rel, p))
        self.assertEqual(bad, [], "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
