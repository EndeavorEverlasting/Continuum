"""Deterministic completion gates over reported evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

ALLOWED_EVIDENCE_STATUSES = frozenset({"passed", "failed", "skipped"})


class CompletionGateError(RuntimeError):
    """Raised when evidence cannot be normalized safely."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class EvidenceRecord:
    """One caller-reported evidence result with a durable reference."""

    name: str
    status: str
    reference: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "reference": self.reference,
            "source": "caller-reported",
        }


@dataclass(frozen=True)
class CompletionGate:
    """Conservative decision over the evidence required by a task packet."""

    status: str
    required: tuple[str, ...]
    passed: tuple[str, ...]
    failed: tuple[str, ...]
    skipped: tuple[str, ...]
    missing: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required": list(self.required),
            "passed": list(self.passed),
            "failed": list(self.failed),
            "skipped": list(self.skipped),
            "missing": list(self.missing),
            "blockers": list(self.blockers),
        }


def _normalize_nonempty_string(value: Any, *, code: str, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompletionGateError(code, message)
    return value.strip()


def parse_evidence_argument(value: str) -> EvidenceRecord:
    """Parse NAME=STATUS=REFERENCE without interpreting the reference."""

    if not isinstance(value, str):
        raise CompletionGateError("evidence.format", "Evidence arguments must be strings.")
    name, separator, remainder = value.partition("=")
    status, second_separator, reference = remainder.partition("=")
    if not separator or not second_separator:
        raise CompletionGateError(
            "evidence.format",
            "Evidence must use NAME=STATUS=REFERENCE format.",
        )
    name = _normalize_nonempty_string(
        name,
        code="evidence.name_empty",
        message="Evidence names must not be empty.",
    )
    status = _normalize_nonempty_string(
        status,
        code="evidence.status_invalid",
        message="Evidence status must not be empty.",
    )
    reference = _normalize_nonempty_string(
        reference,
        code="evidence.reference_missing",
        message=f"Evidence {name!r} must include a non-empty reference.",
    )
    if status not in ALLOWED_EVIDENCE_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_STATUSES))
        raise CompletionGateError(
            "evidence.status_invalid",
            f"Evidence {name!r} has unsupported status {status!r}. Allowed: {allowed}.",
        )
    return EvidenceRecord(name=name, status=status, reference=reference)


def _normalize_required_evidence(required_evidence: Iterable[str]) -> tuple[str, ...]:
    if isinstance(required_evidence, (str, bytes)):
        raise CompletionGateError(
            "completion_gate.required_invalid",
            "Required evidence must be an iterable of names, not a single string.",
        )
    required: list[str] = []
    try:
        items = tuple(required_evidence)
    except TypeError as exc:
        raise CompletionGateError(
            "completion_gate.required_invalid",
            "Required evidence must be iterable.",
        ) from exc
    for item in items:
        required.append(
            _normalize_nonempty_string(
                item,
                code="completion_gate.required_invalid",
                message="Required evidence names must be non-empty strings.",
            )
        )
    normalized = tuple(sorted(required))
    if not normalized:
        raise CompletionGateError(
            "completion_gate.required_missing",
            "A completion gate requires at least one evidence name.",
        )
    if len(set(normalized)) != len(normalized):
        raise CompletionGateError(
            "completion_gate.required_duplicate",
            "The required-evidence list contains duplicates.",
        )
    return normalized


def _normalize_record(record: EvidenceRecord) -> EvidenceRecord:
    if not isinstance(record, EvidenceRecord):
        raise CompletionGateError(
            "evidence.record_invalid",
            "Evidence records must be EvidenceRecord instances.",
        )
    name = _normalize_nonempty_string(
        record.name,
        code="evidence.name_empty",
        message="Evidence names must not be empty.",
    )
    status = _normalize_nonempty_string(
        record.status,
        code="evidence.status_invalid",
        message=f"Evidence {name!r} must include a status.",
    )
    if status not in ALLOWED_EVIDENCE_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_STATUSES))
        raise CompletionGateError(
            "evidence.status_invalid",
            f"Evidence {name!r} has unsupported status {status!r}. Allowed: {allowed}.",
        )
    reference = _normalize_nonempty_string(
        record.reference,
        code="evidence.reference_missing",
        message=f"Evidence {name!r} must include a non-empty reference.",
    )
    return EvidenceRecord(name=name, status=status, reference=reference)


def evaluate_completion_gate(
    required_evidence: Iterable[str],
    evidence_records: Iterable[EvidenceRecord],
    *,
    applicable: bool,
) -> CompletionGate:
    """Evaluate reported evidence without treating it as independent proof."""

    required = _normalize_required_evidence(required_evidence)
    if isinstance(evidence_records, (str, bytes)):
        raise CompletionGateError(
            "evidence.records_invalid",
            "Evidence records must be an iterable of EvidenceRecord values.",
        )
    try:
        items = tuple(evidence_records)
    except TypeError as exc:
        raise CompletionGateError(
            "evidence.records_invalid",
            "Evidence records must be iterable.",
        ) from exc

    records: dict[str, EvidenceRecord] = {}
    for raw_record in items:
        record = _normalize_record(raw_record)
        if record.name in records:
            raise CompletionGateError(
                "evidence.duplicate",
                f"Evidence {record.name!r} was reported more than once.",
            )
        if record.name not in required:
            raise CompletionGateError(
                "evidence.unknown",
                f"Evidence {record.name!r} is not required by the task packet.",
            )
        records[record.name] = record

    passed = tuple(sorted(name for name, record in records.items() if record.status == "passed"))
    failed = tuple(sorted(name for name, record in records.items() if record.status == "failed"))
    skipped = tuple(sorted(name for name, record in records.items() if record.status == "skipped"))
    missing = tuple(sorted(set(required) - set(records)))

    if not applicable:
        status = "not_applicable"
        blockers: tuple[str, ...] = ()
    else:
        blocker_list = [f"missing evidence: {name}" for name in missing]
        blocker_list.extend(f"failed evidence: {name}" for name in failed)
        blocker_list.extend(f"skipped evidence: {name}" for name in skipped)
        if blocker_list:
            status = "blocked"
        else:
            status = "unverified"
            blocker_list.append("independent evidence verification required")
        blockers = tuple(blocker_list)

    return CompletionGate(
        status=status,
        required=required,
        passed=passed,
        failed=failed,
        skipped=skipped,
        missing=missing,
        blockers=blockers,
    )
