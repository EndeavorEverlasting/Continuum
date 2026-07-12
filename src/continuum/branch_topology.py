"""Deterministic branch-topology policy and decision gates."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

TOPOLOGY_SCHEMA_VERSION = 1
STACKING_POLICIES = frozenset({"forbidden", "explicit_only", "allowed"})
CHECK_STATES = frozenset({"success", "failure", "pending", "unknown"})
SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


class BranchTopologyError(RuntimeError):
    """A structured blocker for invalid policy or topology evidence."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TOPOLOGY_SCHEMA_VERSION,
            "command": "topology",
            "status": "blocked",
            "blocker": {"code": self.code, "message": str(self)},
        }


@dataclass(frozen=True)
class BranchPolicy:
    canonical_base: str
    stacked_pull_requests: str
    merge_green_predecessors_before_next_sprint: bool
    require_clean_base: bool
    require_current_canonical_base: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_base": self.canonical_base,
            "stacked_pull_requests": self.stacked_pull_requests,
            "merge_green_predecessors_before_next_sprint": (
                self.merge_green_predecessors_before_next_sprint
            ),
            "require_clean_base": self.require_clean_base,
            "require_current_canonical_base": self.require_current_canonical_base,
        }


@dataclass(frozen=True)
class PullRequestState:
    number: int
    head: str
    base: str
    state: str
    mergeable: bool
    checks: str


@dataclass(frozen=True)
class TopologySnapshot:
    canonical_name: str
    canonical_head_sha: str
    proposed_name: str
    proposed_head_sha: str
    proposed_dirty: bool
    stacking_exception_allowed: bool
    stacking_exception_reason: str | None
    open_pull_requests: tuple[PullRequestState, ...]


@dataclass(frozen=True)
class BranchTopologyDecision:
    decision: str
    allowed: bool
    canonical_base: str
    canonical_head_sha: str
    proposed_base: str
    proposed_head_sha: str
    predecessor_pr: int | None
    stacking_exception_used: bool
    reason: str
    next_action: str

    @property
    def status(self) -> str:
        return "ready" if self.allowed else "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "schemas/branch-topology-decision.schema.json",
            "schema_version": TOPOLOGY_SCHEMA_VERSION,
            "kind": "continuum.branch-topology-decision",
            "status": self.status,
            "decision": self.decision,
            "allowed": self.allowed,
            "canonical_base": {
                "name": self.canonical_base,
                "head_sha": self.canonical_head_sha,
            },
            "proposed_base": {
                "name": self.proposed_base,
                "head_sha": self.proposed_head_sha,
            },
            "predecessor_pr": self.predecessor_pr,
            "stacking_exception_used": self.stacking_exception_used,
            "reason": self.reason,
            "next_action": self.next_action,
        }

    def render_english(self) -> str:
        lines = [
            f"Continuum evaluated proposed base {self.proposed_base} against {self.canonical_base}.",
            f"Continuum selected topology decision {self.decision}.",
            f"The branch operation is {'allowed' if self.allowed else 'blocked'}.",
            self.reason,
            f"NEXT: {self.next_action}",
        ]
        if self.predecessor_pr is not None:
            lines.append(f"The predecessor is pull request #{self.predecessor_pr}.")
        return "\n".join(lines)


def _nonempty_string(value: Any, *, code: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BranchTopologyError(code, f"{label} must be a non-empty string.")
    return value.strip()


def _boolean(value: Any, *, code: str, label: str) -> bool:
    if not isinstance(value, bool):
        raise BranchTopologyError(code, f"{label} must be a boolean.")
    return value


def _sha(value: Any, *, code: str, label: str) -> str:
    normalized = _nonempty_string(value, code=code, label=label)
    if not SHA_PATTERN.fullmatch(normalized):
        raise BranchTopologyError(code, f"{label} must be a lowercase hexadecimal Git SHA.")
    return normalized


def parse_branch_policy(document: Mapping[str, Any]) -> BranchPolicy:
    """Parse branch policy from a repository contract document."""

    raw = document.get("branch_policy")
    if not isinstance(raw, dict):
        raise BranchTopologyError(
            "branch_policy.missing",
            "The repository contract must contain a branch_policy object.",
        )
    canonical = _nonempty_string(
        raw.get("canonical_base"),
        code="branch_policy.canonical_base",
        label="Canonical base",
    )
    stacking = _nonempty_string(
        raw.get("stacked_pull_requests"),
        code="branch_policy.stacking",
        label="Stacked pull-request policy",
    )
    if stacking not in STACKING_POLICIES:
        allowed = ", ".join(sorted(STACKING_POLICIES))
        raise BranchTopologyError(
            "branch_policy.stacking",
            f"Stacked pull-request policy must be one of: {allowed}.",
        )
    repository = document.get("repository")
    default_branch = repository.get("default_branch") if isinstance(repository, dict) else None
    if canonical != default_branch:
        raise BranchTopologyError(
            "branch_policy.canonical_mismatch",
            "branch_policy.canonical_base must match repository.default_branch.",
        )
    return BranchPolicy(
        canonical_base=canonical,
        stacked_pull_requests=stacking,
        merge_green_predecessors_before_next_sprint=_boolean(
            raw.get("merge_green_predecessors_before_next_sprint"),
            code="branch_policy.merge_green",
            label="Merge-green-predecessors policy",
        ),
        require_clean_base=_boolean(
            raw.get("require_clean_base"),
            code="branch_policy.require_clean_base",
            label="Require-clean-base policy",
        ),
        require_current_canonical_base=_boolean(
            raw.get("require_current_canonical_base"),
            code="branch_policy.require_current_canonical_base",
            label="Require-current-canonical-base policy",
        ),
    )


def load_branch_policy(repository_root: Path) -> BranchPolicy:
    path = repository_root.expanduser().resolve() / ".continuum" / "repository.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BranchTopologyError(
            "branch_policy.contract_missing",
            f"The repository contract does not exist at {path}.",
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BranchTopologyError(
            "branch_policy.contract_parse",
            f"The repository contract could not be parsed: {exc}.",
        ) from exc
    if not isinstance(document, dict):
        raise BranchTopologyError(
            "branch_policy.contract_type",
            "The repository contract must be a JSON object.",
        )
    return parse_branch_policy(document)


def _parse_pull_request(value: Any) -> PullRequestState:
    if not isinstance(value, dict):
        raise BranchTopologyError(
            "topology.pull_request_type",
            "Each pull-request snapshot must be an object.",
        )
    number = value.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise BranchTopologyError(
            "topology.pull_request_number",
            "Pull-request numbers must be positive integers.",
        )
    state = _nonempty_string(
        value.get("state"), code="topology.pull_request_state", label="Pull-request state"
    )
    if state != "open":
        raise BranchTopologyError(
            "topology.pull_request_state",
            "Topology snapshots may contain only open pull requests.",
        )
    checks = _nonempty_string(
        value.get("checks"), code="topology.pull_request_checks", label="Check state"
    )
    if checks not in CHECK_STATES:
        allowed = ", ".join(sorted(CHECK_STATES))
        raise BranchTopologyError(
            "topology.pull_request_checks",
            f"Check state must be one of: {allowed}.",
        )
    return PullRequestState(
        number=number,
        head=_nonempty_string(
            value.get("head"), code="topology.pull_request_head", label="PR head"
        ),
        base=_nonempty_string(
            value.get("base"), code="topology.pull_request_base", label="PR base"
        ),
        state=state,
        mergeable=_boolean(
            value.get("mergeable"),
            code="topology.pull_request_mergeable",
            label="PR mergeable state",
        ),
        checks=checks,
    )


def parse_topology_snapshot(document: Mapping[str, Any]) -> TopologySnapshot:
    if document.get("schema_version") != TOPOLOGY_SCHEMA_VERSION:
        raise BranchTopologyError(
            "topology.schema_version",
            f"Topology schema_version must be {TOPOLOGY_SCHEMA_VERSION}.",
        )
    if document.get("kind") != "continuum.branch-topology-snapshot":
        raise BranchTopologyError(
            "topology.kind",
            "The input is not a Continuum branch-topology snapshot.",
        )
    canonical = document.get("canonical_branch")
    proposed = document.get("proposed_base")
    exception = document.get("stacking_exception")
    if not isinstance(canonical, dict) or not isinstance(proposed, dict):
        raise BranchTopologyError(
            "topology.branch_objects",
            "canonical_branch and proposed_base must be objects.",
        )
    if not isinstance(exception, dict):
        raise BranchTopologyError(
            "topology.stacking_exception",
            "stacking_exception must be an object.",
        )
    exception_allowed = _boolean(
        exception.get("allowed"),
        code="topology.stacking_exception",
        label="Stacking exception allowed",
    )
    reason_value = exception.get("reason")
    if reason_value is not None and not isinstance(reason_value, str):
        raise BranchTopologyError(
            "topology.stacking_exception_reason",
            "Stacking exception reason must be a string or null.",
        )
    reason = reason_value.strip() if isinstance(reason_value, str) and reason_value.strip() else None
    if exception_allowed and not reason:
        raise BranchTopologyError(
            "topology.stacking_exception_reason",
            "An allowed stacking exception requires a non-empty reason.",
        )
    if not exception_allowed and reason:
        raise BranchTopologyError(
            "topology.stacking_exception_conflict",
            "A disallowed stacking exception must not include a reason.",
        )
    pulls = document.get("open_pull_requests")
    if not isinstance(pulls, list):
        raise BranchTopologyError(
            "topology.pull_requests_type",
            "open_pull_requests must be an array.",
        )
    parsed_pulls = tuple(_parse_pull_request(item) for item in pulls)
    numbers = [item.number for item in parsed_pulls]
    if len(set(numbers)) != len(numbers):
        raise BranchTopologyError(
            "topology.pull_request_duplicate",
            "Pull-request numbers must be unique.",
        )
    return TopologySnapshot(
        canonical_name=_nonempty_string(
            canonical.get("name"), code="topology.canonical_name", label="Canonical branch name"
        ),
        canonical_head_sha=_sha(
            canonical.get("head_sha"),
            code="topology.canonical_sha",
            label="Canonical branch HEAD",
        ),
        proposed_name=_nonempty_string(
            proposed.get("name"), code="topology.proposed_name", label="Proposed base name"
        ),
        proposed_head_sha=_sha(
            proposed.get("head_sha"),
            code="topology.proposed_sha",
            label="Proposed base HEAD",
        ),
        proposed_dirty=_boolean(
            proposed.get("dirty"), code="topology.proposed_dirty", label="Proposed base dirty state"
        ),
        stacking_exception_allowed=exception_allowed,
        stacking_exception_reason=reason,
        open_pull_requests=parsed_pulls,
    )


def load_topology_snapshot(path: Path) -> TopologySnapshot:
    resolved = path.expanduser().resolve()
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BranchTopologyError(
            "topology.snapshot_missing",
            f"The topology snapshot does not exist at {resolved}.",
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BranchTopologyError(
            "topology.snapshot_parse",
            f"The topology snapshot could not be parsed: {exc}.",
        ) from exc
    if not isinstance(document, dict):
        raise BranchTopologyError(
            "topology.snapshot_type",
            "The topology snapshot must be a JSON object.",
        )
    return parse_topology_snapshot(document)


def _decision(
    snapshot: TopologySnapshot,
    *,
    decision: str,
    allowed: bool,
    predecessor_pr: int | None,
    stacking_exception_used: bool,
    reason: str,
    next_action: str,
) -> BranchTopologyDecision:
    return BranchTopologyDecision(
        decision=decision,
        allowed=allowed,
        canonical_base=snapshot.canonical_name,
        canonical_head_sha=snapshot.canonical_head_sha,
        proposed_base=snapshot.proposed_name,
        proposed_head_sha=snapshot.proposed_head_sha,
        predecessor_pr=predecessor_pr,
        stacking_exception_used=stacking_exception_used,
        reason=reason,
        next_action=next_action,
    )


def evaluate_branch_topology(
    policy: BranchPolicy, snapshot: TopologySnapshot
) -> BranchTopologyDecision:
    """Decide whether a proposed branch base is permitted without mutating GitHub."""

    if snapshot.canonical_name != policy.canonical_base:
        raise BranchTopologyError(
            "topology.canonical_mismatch",
            "The snapshot canonical branch does not match repository branch policy.",
        )
    if policy.require_clean_base and snapshot.proposed_dirty:
        return _decision(
            snapshot,
            decision="clean_base_required",
            allowed=False,
            predecessor_pr=None,
            stacking_exception_used=False,
            reason="Branch creation cannot start from a dirty base.",
            next_action=f"Clean {snapshot.proposed_name} or create an isolated clean worktree.",
        )
    if snapshot.proposed_name == policy.canonical_base:
        if (
            policy.require_current_canonical_base
            and snapshot.proposed_head_sha != snapshot.canonical_head_sha
        ):
            return _decision(
                snapshot,
                decision="refresh_canonical_base",
                allowed=False,
                predecessor_pr=None,
                stacking_exception_used=False,
                reason="The proposed canonical base is stale.",
                next_action=f"Refresh {policy.canonical_base} to {snapshot.canonical_head_sha}.",
            )
        return _decision(
            snapshot,
            decision="create_branch_from_canonical",
            allowed=True,
            predecessor_pr=None,
            stacking_exception_used=False,
            reason="The proposed base is the clean, current canonical branch.",
            next_action=f"Create the sprint branch from {policy.canonical_base}.",
        )

    predecessor = next(
        (
            pull
            for pull in snapshot.open_pull_requests
            if pull.head == snapshot.proposed_name and pull.base == policy.canonical_base
        ),
        None,
    )
    if (
        predecessor is not None
        and policy.merge_green_predecessors_before_next_sprint
        and predecessor.mergeable
        and predecessor.checks == "success"
    ):
        return _decision(
            snapshot,
            decision="merge_predecessor_first",
            allowed=False,
            predecessor_pr=predecessor.number,
            stacking_exception_used=False,
            reason="The proposed feature base has a green, mergeable pull request.",
            next_action=(
                f"Merge pull request #{predecessor.number}, refresh {policy.canonical_base}, "
                f"and create the next branch from {policy.canonical_base}."
            ),
        )
    if policy.stacked_pull_requests == "forbidden":
        return _decision(
            snapshot,
            decision="stacking_forbidden",
            allowed=False,
            predecessor_pr=predecessor.number if predecessor else None,
            stacking_exception_used=False,
            reason="Repository policy forbids stacked pull requests.",
            next_action=f"Use {policy.canonical_base} as the proposed base.",
        )
    if policy.stacked_pull_requests == "explicit_only":
        if not snapshot.stacking_exception_allowed:
            return _decision(
                snapshot,
                decision="stacking_exception_required",
                allowed=False,
                predecessor_pr=predecessor.number if predecessor else None,
                stacking_exception_used=False,
                reason="A non-canonical base requires an explicit stacking exception.",
                next_action=(
                    f"Use {policy.canonical_base}, or record a bounded stacking exception with a reason."
                ),
            )
        return _decision(
            snapshot,
            decision="allow_explicit_stack",
            allowed=True,
            predecessor_pr=predecessor.number if predecessor else None,
            stacking_exception_used=True,
            reason=snapshot.stacking_exception_reason or "An explicit stacking exception was supplied.",
            next_action=f"Create the explicitly authorized stacked branch from {snapshot.proposed_name}.",
        )
    return _decision(
        snapshot,
        decision="allow_policy_stack",
        allowed=True,
        predecessor_pr=predecessor.number if predecessor else None,
        stacking_exception_used=snapshot.stacking_exception_allowed,
        reason="Repository policy permits stacked pull requests.",
        next_action=f"Create the stacked branch from {snapshot.proposed_name}.",
    )
