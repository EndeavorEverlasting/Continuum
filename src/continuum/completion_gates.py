"""Deterministic completion gates over caller-reported evidence records."""

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
    """Structural decision over the evidence required by a task packet."""

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


def parse_evidence_argument(value: str) -> EvidenceRecord:
    """Parse NAME=STATUS=REFERENCE without interpreting the reference."""

    name, separator, remainder = value.partition("=")
    status, second_separator, reference = remainder.partition("=")
    name = name.strip()
    status = status.strip()
    reference = reference.strip()
    if not separator or not second_separator:
        raise CompletionGateError(
            "evidence.format",
            "Evidence must use NAME=STATUS=REFERENCE format.",
        )
    if not name:
        raise CompletionGateError("evidence.name_empty", "Evidence names must not be empty.")
    if status not in ALLOWED_EVIDENCE_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_STATUSES))
        raise CompletionGateError(
            "evidence.status_invalid",
            f"Evidence {name!r} has unsupported status {status!r}. Allowed: {allowed}.",
        )
    if not reference:
        raise CompletionGateError(
            "evidence.reference_missing",
            f"Evidence {name!r} must include a non-empty reference.",
        )
    return EvidenceRecord(name=name, status=status, reference=reference)


def evaluate_completion_gate(
    required_evidence: Iterable[str],
    evidence_records: Iterable[EvidenceRecord],
    *,
    applicable: bool,
) -> CompletionGate:
    """Evaluate whether every required evidence record structurally passed."""

    required = tuple(sorted(item.strip() for item in required_evidence if item.strip()))
    if not required:
        raise CompletionGateError(
            "completion_gate.required_missing",
            "A completion gate requires at least one evidence name.",
        )
    if len(set(required)) != len(required):
        raise CompletionGateError(
            "completion_gate.required_duplicate",
            "The required-evidence list contains duplicates.",
        )

    records: dict[str, EvidenceRecord] = {}
    for record in evidence_records:
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
        blockers = tuple(blocker_list)
        status = "passed" if not blockers else "blocked"

    return CompletionGate(
        status=status,
        required=required,
        passed=passed,
        failed=failed,
        skipped=skipped,
        missing=missing,
        blockers=blockers,
    )
