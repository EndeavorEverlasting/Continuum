"""Explicit workflow-transition decisions without persistent state mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_OUTCOMES = frozenset({"succeeded", "blocked", "failed"})


class WorkflowError(RuntimeError):
    """Raised when a result cannot map to a declared transition."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class WorkflowTransition:
    from_state: str
    to_state: str
    decision: str
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_state,
            "to": self.to_state,
            "decision": self.decision,
            "applied": self.applied,
        }


def decide_result_transition(
    *,
    task_status: str,
    outcome: str,
    completion_gate_status: str,
) -> WorkflowTransition:
    """Decide a transition while leaving durable workflow state untouched."""

    if task_status != "ready":
        raise WorkflowError(
            "workflow.task_state_invalid",
            f"Result packets require a ready task packet, not {task_status!r}.",
        )
    if outcome not in ALLOWED_OUTCOMES:
        allowed = ", ".join(sorted(ALLOWED_OUTCOMES))
        raise WorkflowError(
            "workflow.outcome_invalid",
            f"Unsupported outcome {outcome!r}. Allowed: {allowed}.",
        )

    if outcome == "succeeded":
        return WorkflowTransition(
            from_state="ready",
            to_state="completed",
            decision="allowed" if completion_gate_status == "passed" else "blocked",
        )

    return WorkflowTransition(
        from_state="ready",
        to_state="blocked",
        decision="allowed",
    )
