from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.workflows import WorkflowError, decide_result_transition  # noqa: E402


class WorkflowTests(unittest.TestCase):
    def test_only_verified_passed_gate_allows_completion(self) -> None:
        transition = decide_result_transition(
            task_status="ready",
            outcome="succeeded",
            completion_gate_status="passed",
        )
        self.assertEqual("completed", transition.to_state)
        self.assertEqual("allowed", transition.decision)
        self.assertFalse(transition.applied)

    def test_unverified_success_does_not_allow_completion(self) -> None:
        transition = decide_result_transition(
            task_status="ready",
            outcome="succeeded",
            completion_gate_status="unverified",
        )
        self.assertEqual("completed", transition.to_state)
        self.assertEqual("blocked", transition.decision)

    def test_failed_outcome_allows_blocked_terminal_transition(self) -> None:
        transition = decide_result_transition(
            task_status="ready",
            outcome="failed",
            completion_gate_status="not_applicable",
        )
        self.assertEqual("blocked", transition.to_state)
        self.assertEqual("allowed", transition.decision)

    def test_rejects_non_ready_task_state(self) -> None:
        with self.assertRaises(WorkflowError) as raised:
            decide_result_transition(
                task_status="completed",
                outcome="succeeded",
                completion_gate_status="passed",
            )
        self.assertEqual("workflow.task_state_invalid", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
