from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.completion_gates import (  # noqa: E402
    CompletionGateError,
    EvidenceRecord,
    evaluate_completion_gate,
    parse_evidence_argument,
)


class CompletionGateTests(unittest.TestCase):
    def test_passes_when_all_required_evidence_passes(self) -> None:
        gate = evaluate_completion_gate(
            ["commit_sha", "validation_results"],
            [
                EvidenceRecord("commit_sha", "passed", "abc123"),
                EvidenceRecord("validation_results", "passed", "artifacts/validation.json"),
            ],
            applicable=True,
        )
        self.assertEqual("passed", gate.status)
        self.assertEqual((), gate.blockers)

    def test_blocks_missing_failed_and_skipped_evidence(self) -> None:
        gate = evaluate_completion_gate(
            ["commit_sha", "git_status", "validation_results"],
            [
                EvidenceRecord("git_status", "failed", "artifacts/status.txt"),
                EvidenceRecord("validation_results", "skipped", "not-run"),
            ],
            applicable=True,
        )
        self.assertEqual("blocked", gate.status)
        self.assertEqual(("commit_sha",), gate.missing)
        self.assertIn("failed evidence: git_status", gate.blockers)
        self.assertIn("skipped evidence: validation_results", gate.blockers)

    def test_rejects_unknown_evidence_name(self) -> None:
        with self.assertRaises(CompletionGateError) as raised:
            evaluate_completion_gate(
                ["validation_results"],
                [EvidenceRecord("typo", "passed", "ref")],
                applicable=True,
            )
        self.assertEqual("evidence.unknown", raised.exception.code)

    def test_parses_reference_with_equals_characters(self) -> None:
        record = parse_evidence_argument("commit_sha=passed=sha=abc123")
        self.assertEqual("sha=abc123", record.reference)


if __name__ == "__main__":
    unittest.main()
