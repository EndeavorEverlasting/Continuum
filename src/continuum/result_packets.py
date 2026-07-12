"""Compilation of immutable result packets and transition decisions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .completion_gates import (
    CompletionGate,
    CompletionGateError,
    EvidenceRecord,
    evaluate_completion_gate,
)
from .workflows import (
    ALLOWED_OUTCOMES,
    WorkflowError,
    WorkflowTransition,
    decide_result_transition,
)

RESULT_PACKET_SCHEMA_VERSION = 1
ALLOWED_DOMAIN_AVAILABILITY = frozenset({"unverified", "observed", "unavailable"})


class ResultPacketError(RuntimeError):
    """A structured blocker that prevents safe result-packet compilation."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RESULT_PACKET_SCHEMA_VERSION,
            "command": "result",
            "status": "blocked",
            "blocker": {"code": self.code, "message": str(self)},
        }


@dataclass(frozen=True)
class DomainObservation:
    """Unverified domain state; verified observations require a future adapter."""

    name: str
    availability: str
    observed_capabilities: tuple[str, ...]
    evidence_reference: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "availability": self.availability,
            "observed_capabilities": list(self.observed_capabilities),
            "evidence_reference": self.evidence_reference,
            "source": "caller-reported",
        }


@dataclass(frozen=True)
class ResultPacket:
    result_id: str
    task_id: str
    repository_name: str
    repository_root: str
    head_sha: str
    outcome: str
    evidence: tuple[EvidenceRecord, ...]
    completion_gate: CompletionGate
    domain_observation: DomainObservation
    transition: WorkflowTransition
    blocker: dict[str, str] | None

    @property
    def status(self) -> str:
        return "ready" if self.transition.decision == "allowed" else "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "schemas/result-packet.schema.json",
            "schema_version": RESULT_PACKET_SCHEMA_VERSION,
            "kind": "continuum.result-packet",
            "result_id": self.result_id,
            "task_id": self.task_id,
            "status": self.status,
            "outcome": self.outcome,
            "repository": {
                "name": self.repository_name,
                "root": self.repository_root,
                "head_sha": self.head_sha,
            },
            "evidence": [record.to_dict() for record in self.evidence],
            "completion_gate": self.completion_gate.to_dict(),
            "domain_observation": self.domain_observation.to_dict(),
            "transition": self.transition.to_dict(),
            "blocker": self.blocker,
        }

    def render_english(self) -> str:
        lines = [
            f"Continuum compiled result packet {self.result_id} for task {self.task_id}.",
            f"The reported outcome is {self.outcome}.",
            (
                f"The execution domain {self.domain_observation.name} remains "
                f"{self.domain_observation.availability}."
            ),
            f"The completion gate is {self.completion_gate.status}.",
            (
                f"The workflow transition from {self.transition.from_state} to "
                f"{self.transition.to_state} is {self.transition.decision}."
            ),
            "Continuum did not apply the workflow transition.",
        ]
        for item in self.completion_gate.blockers:
            lines.append(f"BLOCKER: {item}")
        if self.blocker:
            lines.append(f"BLOCKER [{self.blocker['code']}]: {self.blocker['message']}")
        return "\n".join(lines)


def load_task_packet(path: Path) -> dict[str, Any]:
    """Load a task packet without executing or resolving any referenced content."""

    resolved = path.expanduser().resolve()
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResultPacketError(
            "result.task_packet_missing",
            f"The task packet does not exist at {resolved}.",
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResultPacketError(
            "result.task_packet_parse",
            f"The task packet could not be parsed: {exc}.",
        ) from exc
    if not isinstance(document, dict):
        raise ResultPacketError(
            "result.task_packet_type",
            "The task packet must be a JSON object.",
        )
    return document


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ResultPacketError("result.task_packet_invalid", "Expected a non-empty string list.")
    if not all(_nonempty_string(item) for item in value):
        raise ResultPacketError("result.task_packet_invalid", "Task packet lists must contain strings.")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ResultPacketError("result.task_packet_invalid", "Task packet lists must be unique.")
    return normalized


def _validate_task_packet(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != 1 or document.get("kind") != "continuum.task-packet":
        raise ResultPacketError(
            "result.task_packet_invalid",
            "The input is not a supported Continuum task packet.",
        )
    task_id = document.get("task_id")
    status = document.get("status")
    if not _nonempty_string(task_id) or status != "ready":
        raise ResultPacketError(
            "result.task_packet_invalid",
            "The task packet must have a non-empty task_id and ready status.",
        )

    repository = document.get("repository")
    git = document.get("git")
    contract = document.get("contract")
    execution = document.get("execution")
    if not all(isinstance(item, dict) for item in (repository, git, contract, execution)):
        raise ResultPacketError(
            "result.task_packet_invalid",
            "The task packet is missing repository, Git, contract, or execution objects.",
        )

    required = _string_list(contract.get("required_evidence"))
    capabilities = _string_list(execution.get("capabilities"))
    fields = {
        "task_id": task_id.strip(),
        "task_status": status,
        "repository_name": repository.get("name"),
        "repository_root": repository.get("root"),
        "head_sha": git.get("head_sha"),
        "domain_name": execution.get("name"),
        "declared_capabilities": capabilities,
        "required_evidence": required,
    }
    for name in ("repository_name", "repository_root", "head_sha", "domain_name"):
        if not _nonempty_string(fields[name]):
            raise ResultPacketError(
                "result.task_packet_invalid",
                f"The task packet field {name!r} must be a non-empty string.",
            )
    return fields


def _normalize_observed_capabilities(value: Iterable[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ResultPacketError(
            "domain_observation.capability_type",
            "Observed capabilities must be an iterable of strings, not a single string.",
        )
    try:
        items = tuple(value)
    except TypeError as exc:
        raise ResultPacketError(
            "domain_observation.capability_type",
            "Observed capabilities must be iterable.",
        ) from exc
    normalized: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ResultPacketError(
                "domain_observation.capability_type",
                "Observed capabilities must be non-empty strings.",
            )
        normalized.append(item.strip())
    result = tuple(sorted(normalized))
    if len(set(result)) != len(result):
        raise ResultPacketError(
            "domain_observation.capability_duplicate",
            "Observed domain capabilities must be unique.",
        )
    return result


def _normalize_domain_observation(
    *,
    domain_name: str,
    declared_capabilities: tuple[str, ...],
    availability: str,
    observed_capabilities: Iterable[str],
    evidence_reference: str | None,
) -> DomainObservation:
    if not isinstance(availability, str):
        raise ResultPacketError(
            "domain_observation.availability_type",
            "Domain availability must be a string.",
        )
    availability = availability.strip()
    if availability not in ALLOWED_DOMAIN_AVAILABILITY:
        allowed = ", ".join(sorted(ALLOWED_DOMAIN_AVAILABILITY))
        raise ResultPacketError(
            "domain_observation.availability_invalid",
            f"Unsupported domain availability {availability!r}. Allowed: {allowed}.",
        )
    observed = _normalize_observed_capabilities(observed_capabilities)
    if evidence_reference is not None and not isinstance(evidence_reference, str):
        raise ResultPacketError(
            "domain_observation.evidence_type",
            "Domain evidence references must be strings.",
        )
    reference = evidence_reference.strip() if isinstance(evidence_reference, str) else None

    if availability != "unverified":
        raise ResultPacketError(
            "domain_observation.verifier_required",
            "Observed or unavailable domain state requires an independent domain adapter verifier.",
        )
    if observed or reference:
        raise ResultPacketError(
            "domain_observation.unverified_conflict",
            "An unverified domain cannot include observed capabilities or evidence.",
        )

    return DomainObservation(
        name=domain_name,
        availability=availability,
        observed_capabilities=(),
        evidence_reference=None,
    )


def _optional_text(value: Any, *, code: str, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ResultPacketError(code, f"{label} must be a string when supplied.")
    return value.strip()


def _normalize_blocker(
    outcome: str,
    blocker_code: str | None,
    blocker_message: str | None,
) -> dict[str, str] | None:
    code = _optional_text(blocker_code, code="result.blocker_type", label="Blocker code")
    message = _optional_text(blocker_message, code="result.blocker_type", label="Blocker message")
    if outcome == "succeeded":
        if code or message:
            raise ResultPacketError(
                "result.blocker_conflict",
                "A succeeded result must not include a blocker.",
            )
        return None
    if not code or not message:
        raise ResultPacketError(
            "result.blocker_missing",
            "Blocked and failed outcomes require blocker code and message.",
        )
    return {"code": code, "message": message}


def _derive_result_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"result-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


def compile_result_packet(
    task_packet: Mapping[str, Any],
    *,
    outcome: str,
    evidence_records: Iterable[EvidenceRecord],
    domain_availability: str = "unverified",
    observed_capabilities: Iterable[str] = (),
    domain_evidence_reference: str | None = None,
    blocker_code: str | None = None,
    blocker_message: str | None = None,
) -> ResultPacket:
    """Compile a result packet without executing commands or mutating workflow state."""

    task = _validate_task_packet(task_packet)
    if not isinstance(outcome, str):
        raise ResultPacketError("result.outcome_type", "Result outcome must be a string.")
    outcome = outcome.strip()
    if outcome not in ALLOWED_OUTCOMES:
        allowed = ", ".join(sorted(ALLOWED_OUTCOMES))
        raise ResultPacketError(
            "result.outcome_invalid",
            f"Unsupported outcome {outcome!r}. Allowed: {allowed}.",
        )
    blocker = _normalize_blocker(outcome, blocker_code, blocker_message)
    if isinstance(evidence_records, (str, bytes)):
        raise ResultPacketError(
            "evidence.records_invalid",
            "Evidence records must be an iterable of EvidenceRecord values.",
        )
    try:
        records = tuple(sorted(tuple(evidence_records), key=lambda record: record.name))
    except (TypeError, AttributeError) as exc:
        raise ResultPacketError(
            "evidence.records_invalid",
            "Evidence records must be sortable EvidenceRecord values.",
        ) from exc
    try:
        completion_gate = evaluate_completion_gate(
            task["required_evidence"],
            records,
            applicable=outcome == "succeeded",
        )
    except CompletionGateError as exc:
        raise ResultPacketError(exc.code, str(exc)) from exc

    domain_observation = _normalize_domain_observation(
        domain_name=task["domain_name"],
        declared_capabilities=task["declared_capabilities"],
        availability=domain_availability,
        observed_capabilities=observed_capabilities,
        evidence_reference=domain_evidence_reference,
    )
    try:
        transition = decide_result_transition(
            task_status=task["task_status"],
            outcome=outcome,
            completion_gate_status=completion_gate.status,
        )
    except WorkflowError as exc:
        raise ResultPacketError(exc.code, str(exc)) from exc

    identity = {
        "task_id": task["task_id"],
        "outcome": outcome,
        "evidence": [record.to_dict() for record in records],
        "completion_gate": completion_gate.to_dict(),
        "domain_observation": domain_observation.to_dict(),
        "transition": transition.to_dict(),
        "blocker": blocker,
    }
    return ResultPacket(
        result_id=_derive_result_id(identity),
        task_id=task["task_id"],
        repository_name=task["repository_name"],
        repository_root=task["repository_root"],
        head_sha=task["head_sha"],
        outcome=outcome,
        evidence=records,
        completion_gate=completion_gate,
        domain_observation=domain_observation,
        transition=transition,
        blocker=blocker,
    )
