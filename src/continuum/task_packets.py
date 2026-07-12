"""Compilation of bounded task packets from contracts and local Git evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .contracts import inspect_repository
from .git_evidence import GitEvidence, GitEvidenceError, collect_git_evidence

TASK_PACKET_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RepositoryContract:
    """Validated repository-local policy needed to compile bounded work."""

    root: Path
    path: Path
    schema_version: int
    harness_version: str
    name: str
    default_branch: str
    commands: dict[str, str]
    protected_paths: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    required_evidence: tuple[str, ...]


class TaskPacketError(RuntimeError):
    """A structured blocker that prevents safe task-packet compilation."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_PACKET_SCHEMA_VERSION,
            "command": "task",
            "status": "blocked",
            "blocker": {
                "code": self.code,
                "message": str(self),
            },
        }


@dataclass(frozen=True)
class TaskScope:
    owned: tuple[str, ...]
    forbidden: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "owned": list(self.owned),
            "forbidden": list(self.forbidden),
        }


@dataclass(frozen=True)
class TaskPacket:
    """Provider-neutral work input compiled from durable local evidence."""

    task_id: str
    contract: RepositoryContract
    git: GitEvidence
    scope: TaskScope

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "schemas/task-packet.schema.json",
            "schema_version": TASK_PACKET_SCHEMA_VERSION,
            "kind": "continuum.task-packet",
            "task_id": self.task_id,
            "status": "ready",
            "repository": {
                "name": self.contract.name,
                "root": str(self.contract.root),
                "default_branch": self.contract.default_branch,
                "harness_version": self.contract.harness_version,
            },
            "git": self.git.to_dict(),
            "scope": self.scope.to_dict(),
            "contract": {
                "commands": dict(sorted(self.contract.commands.items())),
                "protected_paths": list(self.contract.protected_paths),
                "forbidden_operations": list(self.contract.forbidden_operations),
                "required_evidence": list(self.contract.required_evidence),
            },
        }

    def render_english(self) -> str:
        branch = self.git.branch or "detached HEAD"
        cleanliness = "dirty" if self.git.dirty else "clean"
        lines = [
            f"Continuum compiled task packet {self.task_id}.",
            f"The task targets repository {self.contract.name} at {self.contract.root}.",
            f"Git HEAD is {self.git.head_sha} on {branch}.",
            f"The Git worktree is {cleanliness} with {len(self.git.status_entries)} status entries.",
            f"The task owns {len(self.scope.owned)} scope entries.",
            f"The task forbids {len(self.scope.forbidden)} scope entries.",
            f"The repository requires {len(self.contract.required_evidence)} evidence artifacts.",
            "Continuum classified the task packet as ready.",
        ]
        for item in self.scope.owned:
            lines.append(f"OWNED: {item}")
        for item in self.scope.forbidden:
            lines.append(f"FORBIDDEN: {item}")
        return "\n".join(lines)


def _normalize_scope(values: Iterable[str], *, label: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values if value.strip())
    if not normalized:
        raise TaskPacketError(
            f"scope.{label}_missing",
            f"At least one non-empty {label} scope entry is required.",
        )
    if len(set(normalized)) != len(normalized):
        raise TaskPacketError(
            f"scope.{label}_duplicate",
            f"The {label} scope contains duplicate entries.",
        )
    return normalized


def _derive_task_id(
    contract: RepositoryContract,
    git: GitEvidence,
    scope: TaskScope,
) -> str:
    identity = {
        "repository": contract.name,
        "head_sha": git.head_sha,
        "branch": git.branch,
        "owned": scope.owned,
        "forbidden": scope.forbidden,
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"task-{digest}"


def compile_task_packet(
    root: Path,
    *,
    owned_scope: Iterable[str],
    forbidden_scope: Iterable[str],
    task_id: str | None = None,
    recent_limit: int = 5,
) -> TaskPacket:
    """Compile a deterministic task packet without modifying the repository."""

    owned = _normalize_scope(owned_scope, label="owned")
    forbidden = _normalize_scope(forbidden_scope, label="forbidden")

    report = inspect_repository(root)
    if not report.ok:
        detail = "; ".join(
            f"{check.check_id}: {check.message}"
            for check in report.checks
            if not check.passed
        )
        raise TaskPacketError(
            "contract.invalid",
            detail or "The repository contract is invalid.",
        )

    document = json.loads(report.contract_path.read_text(encoding="utf-8"))
    repository = document["repository"]
    boundaries = document["boundaries"]
    evidence = document["evidence"]
    contract = RepositoryContract(
        root=report.root,
        path=report.contract_path,
        schema_version=document["schema_version"],
        harness_version=document["harness_version"],
        name=repository["name"],
        default_branch=repository["default_branch"],
        commands=dict(document["commands"]),
        protected_paths=tuple(boundaries["protected_paths"]),
        forbidden_operations=tuple(boundaries["forbidden_operations"]),
        required_evidence=tuple(evidence["required"]),
    )

    try:
        git = collect_git_evidence(contract.root, recent_limit=recent_limit)
    except (GitEvidenceError, ValueError) as exc:
        raise TaskPacketError("git.unavailable", str(exc)) from exc

    if git.repository_root != contract.root:
        raise TaskPacketError(
            "git.root_mismatch",
            (
                f"The contract root {contract.root} does not match the Git root "
                f"{git.repository_root}."
            ),
        )

    scope = TaskScope(owned=owned, forbidden=forbidden)
    resolved_task_id = task_id.strip() if task_id else _derive_task_id(contract, git, scope)
    if not resolved_task_id:
        raise TaskPacketError("task_id.empty", "The task ID must not be empty.")

    return TaskPacket(
        task_id=resolved_task_id,
        contract=contract,
        git=git,
        scope=scope,
    )
