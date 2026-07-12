from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.completion_gates import EvidenceRecord  # noqa: E402
from continuum.result_packets import (  # noqa: E402
    ResultPacketError,
    compile_result_packet,
    load_task_packet,
)


TASK_PACKET = {
    "$schema": "schemas/task-packet.schema.json",
    "schema_version": 1,
    "kind": "continuum.task-packet",
    "task_id": "task-1234",
    "status": "ready",
    "repository": {
        "name": "Example",
        "root": "/repo",
        "default_branch": "main",
        "harness_version": "0.3.0",
    },
    "git": {
        "repository_root": "/repo",
        "branch": "main",
        "detached": False,
        "head_sha": "a" * 40,
        "dirty": False,
        "status_entries": [],
        "recent_commits": [{"sha": "a" * 40, "subject": "initial"}],
    },
    "scope": {"owned": ["result packets"], "forbidden": ["command execution"]},
    "execution": {
        "name": "local-inspection",
        "transport": "local",
        "lifecycle": "external",
        "auto_start": False,
        "availability": "unverified",
        "capabilities": ["inspect"],
    },
    "contract": {
        "commands": {"test": "python -m unittest"},
        "protected_paths": ["LICENSE"],
        "forbidden_operations": ["force_push"],
        "required_evidence": ["commit_sha", "validation_results"],
    },
}


class ResultPacketTests(unittest.TestCase):
    def test_success_is_deterministic_and_allows_completion(self) -> None:
        evidence = [
            EvidenceRecord("commit_sha", "passed", "abc123"),
            EvidenceRecord("validation_results", "passed", "artifacts/validation.json"),
        ]
        first = compile_result_packet(TASK_PACKET, outcome="succeeded", evidence_records=evidence)
        second = compile_result_packet(TASK_PACKET, outcome="succeeded", evidence_records=evidence)
        payload = first.to_dict()
        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual("ready", payload["status"])
        self.assertEqual("completed", payload["transition"]["to"])
        self.assertEqual("allowed", payload["transition"]["decision"])
        self.assertFalse(payload["transition"]["applied"])
        self.assertEqual("unverified", payload["domain_observation"]["availability"])

    def test_missing_evidence_blocks_completion_transition(self) -> None:
        packet = compile_result_packet(
            TASK_PACKET,
            outcome="succeeded",
            evidence_records=[EvidenceRecord("commit_sha", "passed", "abc123")],
        )
        payload = packet.to_dict()
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("blocked", payload["completion_gate"]["status"])
        self.assertEqual(["validation_results"], payload["completion_gate"]["missing"])
        self.assertEqual("blocked", payload["transition"]["decision"])

    def test_blocked_outcome_allows_blocked_transition_with_blocker(self) -> None:
        packet = compile_result_packet(
            TASK_PACKET,
            outcome="blocked",
            evidence_records=[],
            blocker_code="human.intent_required",
            blocker_message="A policy decision is required.",
        )
        payload = packet.to_dict()
        self.assertEqual("ready", payload["status"])
        self.assertEqual("not_applicable", payload["completion_gate"]["status"])
        self.assertEqual("blocked", payload["transition"]["to"])
        self.assertEqual("allowed", payload["transition"]["decision"])

    def test_observed_domain_requires_evidence_and_declared_capability(self) -> None:
        with self.assertRaises(ResultPacketError) as missing:
            compile_result_packet(
                TASK_PACKET,
                outcome="blocked",
                evidence_records=[],
                domain_availability="observed",
                blocker_code="test",
                blocker_message="test",
            )
        self.assertEqual("domain_observation.evidence_missing", missing.exception.code)

        with self.assertRaises(ResultPacketError) as undeclared:
            compile_result_packet(
                TASK_PACKET,
                outcome="blocked",
                evidence_records=[],
                domain_availability="observed",
                observed_capabilities=["spawn"],
                domain_evidence_reference="artifacts/domain.json",
                blocker_code="test",
                blocker_message="test",
            )
        self.assertEqual("domain_observation.capability_undeclared", undeclared.exception.code)

    def test_observed_domain_is_recorded_as_caller_reported(self) -> None:
        packet = compile_result_packet(
            TASK_PACKET,
            outcome="blocked",
            evidence_records=[],
            domain_availability="observed",
            observed_capabilities=["inspect"],
            domain_evidence_reference="artifacts/domain.json",
            blocker_code="test.complete",
            blocker_message="The test intentionally ends blocked.",
        )
        observation = packet.to_dict()["domain_observation"]
        self.assertEqual("caller-reported", observation["source"])
        self.assertEqual(["inspect"], observation["observed_capabilities"])

    def test_rejects_unknown_outcome_before_blocker_validation(self) -> None:
        with self.assertRaises(ResultPacketError) as raised:
            compile_result_packet(TASK_PACKET, outcome="maybe", evidence_records=[])
        self.assertEqual("result.outcome_invalid", raised.exception.code)

    def test_failed_outcome_requires_blocker(self) -> None:
        with self.assertRaises(ResultPacketError) as raised:
            compile_result_packet(TASK_PACKET, outcome="failed", evidence_records=[])
        self.assertEqual("result.blocker_missing", raised.exception.code)

    def test_load_task_packet_reports_parse_errors(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "task.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ResultPacketError) as raised:
                load_task_packet(path)
        self.assertEqual("result.task_packet_parse", raised.exception.code)

    def test_task_packet_round_trip_file(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "task.json"
            path.write_text(json.dumps(TASK_PACKET), encoding="utf-8")
            loaded = load_task_packet(path)
        self.assertEqual("task-1234", loaded["task_id"])


if __name__ == "__main__":
    unittest.main()
