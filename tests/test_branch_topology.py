from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.branch_topology import BranchPolicy, BranchTopologyError, evaluate_branch_topology, parse_topology_snapshot  # noqa: E402

SHA_A = "a" * 40
SHA_B = "b" * 40
POLICY = BranchPolicy("main", "explicit_only", True, True, True)


def snapshot(*, proposed_name="main", proposed_sha=SHA_A, dirty=False, exception=False, reason=None, pulls=None):
    return {
        "$schema": "schemas/branch-topology-snapshot.schema.json",
        "schema_version": 1,
        "kind": "continuum.branch-topology-snapshot",
        "canonical_branch": {"name": "main", "head_sha": SHA_A},
        "proposed_base": {"name": proposed_name, "head_sha": proposed_sha, "dirty": dirty},
        "stacking_exception": {"allowed": exception, "reason": reason},
        "open_pull_requests": pulls or [],
    }


class BranchTopologyTests(unittest.TestCase):
    def test_allows_clean_current_canonical_base(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot()))
        self.assertTrue(decision.allowed)
        self.assertEqual("create_branch_from_canonical", decision.decision)

    def test_blocks_stale_canonical_base(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot(proposed_sha=SHA_B)))
        self.assertEqual("refresh_canonical_base", decision.decision)

    def test_blocks_dirty_base(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot(dirty=True)))
        self.assertEqual("clean_base_required", decision.decision)

    def test_requires_green_predecessor_merge_first(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot(proposed_name="feat/result", proposed_sha=SHA_B, pulls=[{"number": 2, "head": "feat/result", "base": "main", "state": "open", "mergeable": True, "checks": "success"}])))
        self.assertEqual("merge_predecessor_first", decision.decision)
        self.assertEqual(2, decision.predecessor_pr)

    def test_requires_exception_for_noncanonical_base(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot(proposed_name="feat/unmerged", proposed_sha=SHA_B)))
        self.assertEqual("stacking_exception_required", decision.decision)

    def test_allows_reasoned_exception(self):
        decision = evaluate_branch_topology(POLICY, parse_topology_snapshot(snapshot(proposed_name="feat/unmerged", proposed_sha=SHA_B, exception=True, reason="Dependent contract review.")))
        self.assertTrue(decision.allowed)
        self.assertEqual("allow_explicit_stack", decision.decision)

    def test_rejects_exception_without_reason(self):
        with self.assertRaises(BranchTopologyError) as raised:
            parse_topology_snapshot(snapshot(proposed_name="feat/unmerged", proposed_sha=SHA_B, exception=True))
        self.assertEqual("topology.stacking_exception_reason", raised.exception.code)

    def test_rejects_invalid_pull_request_types(self):
        with self.assertRaises(BranchTopologyError) as raised:
            parse_topology_snapshot(snapshot(proposed_name="feat/unmerged", proposed_sha=SHA_B, pulls=[{"number": True, "head": "feat/unmerged", "base": "main", "state": "open", "mergeable": True, "checks": "success"}]))
        self.assertEqual("topology.pull_request_number", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
