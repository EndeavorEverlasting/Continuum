"""Repository-contract inspection for Continuum's executable loop."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

CONTRACT_RELATIVE_PATH = Path(".continuum/repository.json")
SUPPORTED_SCHEMA_VERSION = 1
BRANCH_STACKING_POLICIES = frozenset({"forbidden", "explicit_only", "allowed"})


@dataclass(frozen=True)
class CheckResult:
    """One deterministic contract check."""

    check_id: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.check_id, "passed": self.passed, "message": self.message}


@dataclass(frozen=True)
class InspectionReport:
    """Evidence produced by inspecting one repository contract."""

    root: Path
    contract_path: Path
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        passed = sum(check.passed for check in self.checks)
        failed = len(self.checks) - passed
        return {
            "schema_version": 1,
            "command": "doctor",
            "repository_root": str(self.root),
            "contract_path": str(self.contract_path),
            "status": "ready" if self.ok else "blocked",
            "summary": {"total": len(self.checks), "passed": passed, "failed": failed},
            "checks": [check.to_dict() for check in self.checks],
        }

    def render_english(self) -> str:
        passed = sum(check.passed for check in self.checks)
        failed = len(self.checks) - passed
        status = "ready" if self.ok else "blocked"
        lines = [
            f"Continuum inspected the repository at {self.root}.",
            f"Continuum evaluated the contract at {self.contract_path}.",
            f"Continuum completed {len(self.checks)} checks: {passed} passed and {failed} failed.",
            f"Continuum classified the repository as {status}.",
        ]
        for check in self.checks:
            label = "PASS" if check.passed else "FAIL"
            lines.append(f"{label} [{check.check_id}]: {check.message}")
        return "\n".join(lines)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, allow_empty: bool = True) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(
        _nonempty_string(item) for item in value
    )


def _mapping_of_strings(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(
        _nonempty_string(key) and _nonempty_string(item) for key, item in value.items()
    )


def inspect_repository(root: Path) -> InspectionReport:
    """Inspect a repository without modifying it or invoking network services."""

    resolved_root = root.expanduser().resolve()
    contract_path = resolved_root / CONTRACT_RELATIVE_PATH
    checks: list[CheckResult] = []

    if not contract_path.is_file():
        checks.append(CheckResult("contract.exists", False, "The repository contract does not exist."))
        return InspectionReport(resolved_root, contract_path, tuple(checks))
    checks.append(CheckResult("contract.exists", True, "The repository contract exists."))

    try:
        document = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(CheckResult("contract.parse", False, f"The repository contract could not be parsed: {exc}."))
        return InspectionReport(resolved_root, contract_path, tuple(checks))

    checks.append(CheckResult(
        "contract.parse",
        isinstance(document, dict),
        "The repository contract is a JSON object." if isinstance(document, dict) else "The repository contract must be a JSON object.",
    ))
    if not isinstance(document, dict):
        return InspectionReport(resolved_root, contract_path, tuple(checks))

    schema_version = document.get("schema_version")
    checks.append(CheckResult(
        "contract.schema_version",
        schema_version == SUPPORTED_SCHEMA_VERSION,
        f"The schema version is {SUPPORTED_SCHEMA_VERSION}." if schema_version == SUPPORTED_SCHEMA_VERSION else f"The schema version must be {SUPPORTED_SCHEMA_VERSION}, but it is {schema_version!r}.",
    ))
    harness_version = document.get("harness_version")
    checks.append(CheckResult(
        "contract.harness_version",
        _nonempty_string(harness_version),
        "The harness version is declared." if _nonempty_string(harness_version) else "The harness version must be a non-empty string.",
    ))

    repository = document.get("repository")
    repository_ok = isinstance(repository, dict)
    checks.append(CheckResult(
        "repository.object", repository_ok,
        "The repository section is a JSON object." if repository_ok else "The repository section must be a JSON object.",
    ))
    repository = repository if repository_ok else {}
    name = repository.get("name")
    checks.append(CheckResult(
        "repository.name", _nonempty_string(name),
        "The repository name is declared." if _nonempty_string(name) else "The repository name must be a non-empty string.",
    ))
    default_branch = repository.get("default_branch")
    checks.append(CheckResult(
        "repository.default_branch", _nonempty_string(default_branch),
        "The default branch is declared." if _nonempty_string(default_branch) else "The default branch must be a non-empty string.",
    ))

    branch_policy = document.get("branch_policy")
    branch_policy_ok = isinstance(branch_policy, dict)
    checks.append(CheckResult(
        "branch_policy.object", branch_policy_ok,
        "The branch-policy section is a JSON object." if branch_policy_ok else "The branch-policy section must be a JSON object.",
    ))
    branch_policy = branch_policy if branch_policy_ok else {}
    canonical_base = branch_policy.get("canonical_base")
    canonical_ok = _nonempty_string(canonical_base) and canonical_base == default_branch
    checks.append(CheckResult(
        "branch_policy.canonical_base", canonical_ok,
        "The canonical base matches the default branch." if canonical_ok else "The canonical base must be a non-empty string matching repository.default_branch.",
    ))
    stacking = branch_policy.get("stacked_pull_requests")
    stacking_ok = stacking in BRANCH_STACKING_POLICIES
    checks.append(CheckResult(
        "branch_policy.stacked_pull_requests", stacking_ok,
        "The stacked pull-request policy is declared." if stacking_ok else "The stacked pull-request policy must be forbidden, explicit_only, or allowed.",
    ))
    for key, label in (
        ("merge_green_predecessors_before_next_sprint", "merge-green-predecessors"),
        ("require_clean_base", "require-clean-base"),
        ("require_current_canonical_base", "require-current-canonical-base"),
    ):
        value = branch_policy.get(key)
        checks.append(CheckResult(
            f"branch_policy.{key}", isinstance(value, bool),
            f"The {label} policy is boolean." if isinstance(value, bool) else f"The {label} policy must be boolean.",
        ))

    commands = document.get("commands")
    checks.append(CheckResult(
        "commands.mapping", _mapping_of_strings(commands),
        "The command map contains executable command strings." if _mapping_of_strings(commands) else "The command map must contain at least one named command string.",
    ))

    boundaries = document.get("boundaries")
    boundaries_ok = isinstance(boundaries, dict)
    checks.append(CheckResult(
        "boundaries.object", boundaries_ok,
        "The boundaries section is a JSON object." if boundaries_ok else "The boundaries section must be a JSON object.",
    ))
    boundaries = boundaries if boundaries_ok else {}
    protected_paths = boundaries.get("protected_paths")
    checks.append(CheckResult(
        "boundaries.protected_paths", _string_list(protected_paths),
        "The protected-path list is valid." if _string_list(protected_paths) else "The protected-path list must contain only non-empty strings.",
    ))
    forbidden_operations = boundaries.get("forbidden_operations")
    checks.append(CheckResult(
        "boundaries.forbidden_operations", _string_list(forbidden_operations, allow_empty=False),
        "The forbidden-operation list contains explicit safety boundaries." if _string_list(forbidden_operations, allow_empty=False) else "The forbidden-operation list must contain at least one non-empty string.",
    ))

    evidence = document.get("evidence")
    evidence_ok = isinstance(evidence, dict)
    checks.append(CheckResult(
        "evidence.object", evidence_ok,
        "The evidence section is a JSON object." if evidence_ok else "The evidence section must be a JSON object.",
    ))
    evidence = evidence if evidence_ok else {}
    required_evidence = evidence.get("required")
    checks.append(CheckResult(
        "evidence.required", _string_list(required_evidence, allow_empty=False),
        "The required-evidence list contains explicit proof artifacts." if _string_list(required_evidence, allow_empty=False) else "The required-evidence list must contain at least one non-empty string.",
    ))
    return InspectionReport(resolved_root, contract_path, tuple(checks))
