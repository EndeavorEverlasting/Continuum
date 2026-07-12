"""Provider-neutral execution-domain lifecycle decisions.

The model adopts WezTerm's separation between a domain's declared capabilities
and its observed attached or detached state.  Decisions remain proposals:
Continuum does not attach, detach, spawn, or mutate a domain here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

SNAPSHOT_KIND = "continuum.execution-domain-snapshot"
DECISION_KIND = "continuum.execution-domain-decision"
SCHEMA_VERSION = 1
ALLOWED_STATES = frozenset({"unverified", "detached", "attached", "unavailable"})
ALLOWED_VERIFICATIONS = frozenset(
    {"unverified", "caller_reported", "independently_verified"}
)
ALLOWED_ACTIONS = frozenset({"attach", "detach", "spawn"})
_SNAPSHOT_KEYS = frozenset(
    {
        "$schema",
        "schema_version",
        "kind",
        "domain",
        "state",
        "verification",
        "evidence_reference",
    }
)


class ExecutionDomainLike(Protocol):
    """Minimal execution-domain surface consumed by the decision engine."""

    name: str
    auto_start: bool
    capabilities: tuple[str, ...]


class DomainLifecycleError(ValueError):
    """Structured blocker for invalid domain snapshots or requests."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "blocked",
            "blocker": {"code": self.code, "message": str(self)},
        }


@dataclass(frozen=True)
class DomainSnapshot:
    """Observed state for one named execution domain."""

    domain: str
    state: str
    verification: str
    evidence_reference: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "schemas/execution-domain-snapshot.schema.json",
            "schema_version": SCHEMA_VERSION,
            "kind": SNAPSHOT_KIND,
            "domain": self.domain,
            "state": self.state,
            "verification": self.verification,
            "evidence_reference": self.evidence_reference,
        }


@dataclass(frozen=True)
class DomainActionDecision:
    """A non-mutating attach, detach, or spawn decision."""

    domain: str
    action: str
    allowed: bool
    current_state: str
    resulting_state: str | None
    verification: str
    evidence_reference: str | None
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "schemas/execution-domain-decision.schema.json",
            "schema_version": SCHEMA_VERSION,
            "kind": DECISION_KIND,
            "domain": self.domain,
            "action": self.action,
            "allowed": self.allowed,
            "applied": False,
            "current_state": self.current_state,
            "resulting_state": self.resulting_state,
            "verification": self.verification,
            "evidence_reference": self.evidence_reference,
            "code": self.code,
            "message": self.message,
        }

    def render_english(self) -> str:
        verb = "allowed" if self.allowed else "blocked"
        return (
            f"Continuum {verb} {self.action!r} for execution domain "
            f"{self.domain!r}: {self.message}"
        )


def _trimmed_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DomainLifecycleError(
            "domain_snapshot.text_invalid",
            f"{label} must be a non-empty string.",
        )
    if value != value.strip():
        raise DomainLifecycleError(
            "domain_snapshot.text_invalid",
            f"{label} must not contain surrounding whitespace.",
        )
    return value


def _optional_reference(value: Any) -> str | None:
    if value is None:
        return None
    return _trimmed_text(value, "Domain evidence reference")


def parse_domain_snapshot(document: Any) -> DomainSnapshot:
    """Parse one decoded domain-state snapshot."""

    if not isinstance(document, dict):
        raise DomainLifecycleError(
            "domain_snapshot.object_invalid",
            "The execution-domain snapshot must be a JSON object.",
        )

    unknown = sorted(set(document) - _SNAPSHOT_KEYS)
    if unknown:
        raise DomainLifecycleError(
            "domain_snapshot.unknown_field",
            "The execution-domain snapshot contains unsupported fields: "
            + ", ".join(unknown)
            + ".",
        )
    if document.get("schema_version") != SCHEMA_VERSION:
        raise DomainLifecycleError(
            "domain_snapshot.schema_version",
            f"The execution-domain snapshot schema_version must be {SCHEMA_VERSION}.",
        )
    if document.get("kind") != SNAPSHOT_KIND:
        raise DomainLifecycleError(
            "domain_snapshot.kind_invalid",
            f"The execution-domain snapshot kind must be {SNAPSHOT_KIND!r}.",
        )

    domain = _trimmed_text(document.get("domain"), "Domain name")
    state = document.get("state")
    if state not in ALLOWED_STATES:
        raise DomainLifecycleError(
            "domain_snapshot.state_invalid",
            "Domain state must be one of: "
            + ", ".join(sorted(ALLOWED_STATES))
            + ".",
        )
    verification = document.get("verification")
    if verification not in ALLOWED_VERIFICATIONS:
        raise DomainLifecycleError(
            "domain_snapshot.verification_invalid",
            "Domain verification must be one of: "
            + ", ".join(sorted(ALLOWED_VERIFICATIONS))
            + ".",
        )
    evidence_reference = _optional_reference(document.get("evidence_reference"))

    if state == "unverified":
        if verification != "unverified" or evidence_reference is not None:
            raise DomainLifecycleError(
                "domain_snapshot.unverified_conflict",
                "An unverified domain state must use verification='unverified' "
                "and must not claim an evidence reference.",
            )
    else:
        if verification == "unverified":
            raise DomainLifecycleError(
                "domain_snapshot.verification_missing",
                "A concrete domain state must identify how it was verified.",
            )
        if evidence_reference is None:
            raise DomainLifecycleError(
                "domain_snapshot.evidence_missing",
                "A concrete domain state must include an evidence reference.",
            )

    return DomainSnapshot(
        domain=domain,
        state=state,
        verification=verification,
        evidence_reference=evidence_reference,
    )


def load_domain_snapshot(path: Path) -> DomainSnapshot:
    """Load and validate an execution-domain snapshot from disk."""

    resolved = path.expanduser().resolve()
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DomainLifecycleError(
            "domain_snapshot.missing",
            f"The execution-domain snapshot does not exist at {resolved}.",
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DomainLifecycleError(
            "domain_snapshot.parse",
            f"The execution-domain snapshot could not be parsed: {exc}.",
        ) from exc
    return parse_domain_snapshot(document)


def _decision(
    domain: ExecutionDomainLike,
    snapshot: DomainSnapshot,
    action: str,
    *,
    allowed: bool,
    resulting_state: str | None,
    code: str,
    message: str,
) -> DomainActionDecision:
    return DomainActionDecision(
        domain=domain.name,
        action=action,
        allowed=allowed,
        current_state=snapshot.state,
        resulting_state=resulting_state,
        verification=snapshot.verification,
        evidence_reference=snapshot.evidence_reference,
        code=code,
        message=message,
    )


def evaluate_domain_action(
    domain: ExecutionDomainLike,
    snapshot: DomainSnapshot,
    action: str,
) -> DomainActionDecision:
    """Evaluate one domain action without executing it."""

    if action not in ALLOWED_ACTIONS:
        raise DomainLifecycleError(
            "domain_action.invalid",
            "Domain action must be one of: " + ", ".join(sorted(ALLOWED_ACTIONS)) + ".",
        )
    if snapshot.domain != domain.name:
        raise DomainLifecycleError(
            "domain_action.domain_mismatch",
            f"Snapshot domain {snapshot.domain!r} does not match {domain.name!r}.",
        )
    if action not in set(domain.capabilities):
        return _decision(
            domain,
            snapshot,
            action,
            allowed=False,
            resulting_state=None,
            code="domain_action.capability_missing",
            message=(
                f"The domain does not declare the {action!r} capability. "
                "Declared capabilities remain authoritative."
            ),
        )

    if snapshot.verification != "independently_verified":
        return _decision(
            domain,
            snapshot,
            action,
            allowed=False,
            resulting_state=None,
            code="domain_action.state_unverified",
            message=(
                "State-sensitive actions require independently verified domain state; "
                f"the snapshot is {snapshot.verification!r}."
            ),
        )

    if snapshot.state == "unavailable":
        return _decision(
            domain,
            snapshot,
            action,
            allowed=False,
            resulting_state=None,
            code="domain_action.unavailable",
            message="The independently verified domain is unavailable.",
        )
    if snapshot.state == "unverified":
        return _decision(
            domain,
            snapshot,
            action,
            allowed=False,
            resulting_state=None,
            code="domain_action.state_unverified",
            message="The domain state is unverified.",
        )

    if action == "attach":
        if snapshot.state == "attached":
            return _decision(
                domain,
                snapshot,
                action,
                allowed=True,
                resulting_state="attached",
                code="domain_action.already_attached",
                message="The domain is already attached; no state change is required.",
            )
        return _decision(
            domain,
            snapshot,
            action,
            allowed=True,
            resulting_state="attached",
            code="domain_action.attach_allowed",
            message="The verified detached domain may be attached by a future adapter.",
        )

    if action == "detach":
        if snapshot.state == "detached":
            return _decision(
                domain,
                snapshot,
                action,
                allowed=True,
                resulting_state="detached",
                code="domain_action.already_detached",
                message="The domain is already detached; no state change is required.",
            )
        return _decision(
            domain,
            snapshot,
            action,
            allowed=True,
            resulting_state="detached",
            code="domain_action.detach_allowed",
            message="The verified attached domain may be detached by a future adapter.",
        )

    if snapshot.state == "detached":
        return _decision(
            domain,
            snapshot,
            action,
            allowed=False,
            resulting_state=None,
            code="domain_action.attach_required",
            message=(
                "Spawn requires an attached domain. auto_start controls service "
                "lifecycle and does not imply client attachment."
            ),
        )
    return _decision(
        domain,
        snapshot,
        action,
        allowed=True,
        resulting_state="attached",
        code="domain_action.spawn_allowed",
        message="The verified attached domain may accept a spawn request from a future adapter.",
    )
