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

    def test_r0_outside_first_three_waves(self):
        self.write_feature(MANIFEST.replace("    wave: 3\n    release: R1", "    wave: 4\n    release: R0")
                           .replace("    wave: 2\n    release: R1", "    wave: 3\n    release: R1"))
        self.assertIn(("release.r0_waves", "svc-report"), self.gaps()[0])

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
        self.assertEqual(self.ready_ids(), ["scaffold-app", "agg-order"])
        self.move("agg-order", "doing")
        self.block_wt("agg-order")                    # a branch alone is not integration
        self.assertNotIn("svc-order", self.ready_ids())
        self.commit(os.path.join(self.tmp, "wt", "agg-order"), "src/a.txt", "a\n")
        self.review("agg-order")
        self.compose("start", "agg-order", expect=0)
        self.compose("promote", "agg-order", expect=0)
        self.assertEqual(self.ready_ids(), ["scaffold-app", "svc-order", "rm-orders"])  # wave, then release
        self.put("open-questions/svc-order.md", "which currency?\n")
        out = self.run_tool("ready", self.feat, expect=0)
        self.assertIn("parked", {e["id"]: e["reason"] for e in out["excluded"]}["svc-order"])
        self.put("tasks/be/backlog/perf-spike.md", "---\nid: perf-spike\ntype: spike\ncentral: true\n---\n"
                 "# Spike\n\n## Unblocks\n- rm-orders\n")
        out = self.run_tool("ready", self.feat, expect=0)
        self.assertEqual([r["id"] for r in out["ready"]], ["scaffold-app"])
        self.assertEqual(out["open_spikes"], [{"id": "perf-spike", "state": "backlog", "central": True, "unblocks": ["rm-orders"]}])

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
        """Placeholders → dummies: `<a|b>` → a, `<…>` → x, `record|check` → record, `[opt]` → opt, `GLOB…` → GLOB."""
        rest = re.sub(r"<([^>]*)>", lambda m: m.group(1).split("|")[0] if "|" in m.group(1) else "x", rest)
        out = []
        for tok in shlex.split(rest.replace("[", " ").replace("]", " ")):
            tok = tok.rstrip("…")
            if tok:
                out.append(tok.split("|")[0] if not tok.startswith("-") else tok)
        return out

    def test_every_invocation_parses(self):
        parser, seen, bad = mismagent.build_parser(), 0, []
        for where, span, rest in self.invocations():
            try:
                argv = self.argv(rest)
            except ValueError as e:
                bad.append("%s: `%s` -> %s" % (where, span, e))
                continue
            if len(argv) <= (2 if argv and argv[0] in ("proof", "compose") else 1):
                continue  # a name reference (`MM status`), not an invocation
            seen += 1
            try:
                with open(os.devnull, "w") as null, redirect_stderr(null):
                    parser.parse_args(argv)
            except SystemExit:
                bad.append("%s: `%s` -> %s" % (where, span, argv))
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertGreater(seen, 10)


if __name__ == "__main__":
    unittest.main()
