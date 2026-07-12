"""Validate pinned cross-repository harness contribution manifests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

MANIFEST_KIND = "continuum.harness-contribution-manifest"
MANIFEST_SCHEMA_VERSION = 1
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CONTRIBUTION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
CLASSIFICATIONS = frozenset({"portable_harness", "repo_skill", "domain_specific"})
MATURITY_STATES = frozenset({"merged", "experimental", "deprecated"})
TARGET_LAYERS = frozenset({"continuum_harness", "continuum_skill", "reference_only", "reject"})


class HarnessInteropError(ValueError):
    """Raised when a harness contribution manifest violates its contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class HarnessContribution:
    """One source capability and its intended Continuum disposition."""

    contribution_id: str
    title: str
    source_paths: tuple[str, ...]
    classification: str
    maturity: str
    target_layer: str
    capabilities: tuple[str, ...]
    rationale: str

    @property
    def portable(self) -> bool:
        """Return whether the contribution may enter a Continuum-owned layer."""

        return self.target_layer in {"continuum_harness", "continuum_skill"}


@dataclass(frozen=True)
class HarnessContributionManifest:
    """Pinned donor repository inventory for bounded harness factoring."""

    source_repository: str
    source_commit_sha: str
    authority_paths: tuple[str, ...]
    contributions: tuple[HarnessContribution, ...]

    @property
    def portable_contributions(self) -> tuple[HarnessContribution, ...]:
        """Return contributions eligible for bounded Continuum factoring."""

        return tuple(item for item in self.contributions if item.portable)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HarnessInteropError("interop.object_invalid", f"{label} must be a JSON object.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessInteropError("interop.text_invalid", f"{label} must be a non-empty string.")
    if value != value.strip():
        raise HarnessInteropError("interop.text_invalid", f"{label} must not contain surrounding whitespace.")
    return value


def _enum(value: Any, label: str, allowed: frozenset[str]) -> str:
    parsed = _text(value, label)
    if parsed not in allowed:
        options = ", ".join(sorted(allowed))
        raise HarnessInteropError("interop.enum_invalid", f"{label} must be one of: {options}.")
    return parsed


def _repository(value: Any) -> str:
    parsed = _text(value, "Source repository")
    if not REPOSITORY_PATTERN.fullmatch(parsed):
        raise HarnessInteropError("interop.repository_invalid", "Source repository must use owner/name form.")
    return parsed


def _commit_sha(value: Any) -> str:
    parsed = _text(value, "Source commit SHA")
    if not COMMIT_PATTERN.fullmatch(parsed):
        raise HarnessInteropError(
            "interop.commit_invalid",
            "Source commit SHA must be exactly 40 lowercase hexadecimal characters.",
        )
    return parsed


def _relative_path(value: Any, label: str) -> str:
    parsed = _text(value, label)
    if "\\" in parsed or "//" in parsed:
        raise HarnessInteropError("interop.path_invalid", f"{label} must be a normalized POSIX repository path.")
    path = PurePosixPath(parsed)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HarnessInteropError("interop.path_invalid", f"{label} must stay inside the source repository.")
    if path.as_posix() != parsed:
        raise HarnessInteropError("interop.path_invalid", f"{label} must be a normalized POSIX repository path.")
    return parsed


def _string_list(value: Any, label: str, *, paths: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise HarnessInteropError("interop.list_invalid", f"{label} must be a non-empty array.")
    parsed = tuple(
        _relative_path(item, f"{label} entry") if paths else _text(item, f"{label} entry")
        for item in value
    )
    if len(set(parsed)) != len(parsed):
        raise HarnessInteropError("interop.list_duplicate", f"{label} entries must be unique.")
    return parsed


def _contribution(value: Any) -> HarnessContribution:
    document = _mapping(value, "Contribution")
    allowed_keys = {
        "id",
        "title",
        "source_paths",
        "classification",
        "maturity",
        "target_layer",
        "capabilities",
        "rationale",
    }
    extra = sorted(set(document) - allowed_keys)
    if extra:
        raise HarnessInteropError(
            "interop.contribution_extra",
            f"Contribution contains unsupported fields: {', '.join(extra)}.",
        )

    contribution_id = _text(document.get("id"), "Contribution id")
    if not CONTRIBUTION_ID_PATTERN.fullmatch(contribution_id):
        raise HarnessInteropError(
            "interop.contribution_id_invalid",
            "Contribution id must be a lowercase dotted or hyphenated identifier.",
        )
    classification = _enum(document.get("classification"), "Contribution classification", CLASSIFICATIONS)
    maturity = _enum(document.get("maturity"), "Contribution maturity", MATURITY_STATES)
    target_layer = _enum(document.get("target_layer"), "Contribution target layer", TARGET_LAYERS)

    if maturity != "merged" and target_layer in {"continuum_harness", "continuum_skill"}:
        raise HarnessInteropError(
            "interop.maturity_gate",
            "Only merged donor capabilities may target a Continuum-owned layer.",
        )
    if target_layer == "continuum_harness" and classification != "portable_harness":
        raise HarnessInteropError(
            "interop.harness_boundary",
            "Only portable_harness contributions may target continuum_harness.",
        )
    if target_layer == "continuum_skill" and classification not in {"portable_harness", "repo_skill"}:
        raise HarnessInteropError(
            "interop.skill_boundary",
            "Domain-specific contributions cannot target continuum_skill.",
        )

    return HarnessContribution(
        contribution_id=contribution_id,
        title=_text(document.get("title"), "Contribution title"),
        source_paths=_string_list(document.get("source_paths"), "Contribution source paths", paths=True),
        classification=classification,
        maturity=maturity,
        target_layer=target_layer,
        capabilities=_string_list(document.get("capabilities"), "Contribution capabilities"),
        rationale=_text(document.get("rationale"), "Contribution rationale"),
    )


def parse_harness_contribution_manifest(document: Any) -> HarnessContributionManifest:
    """Parse and validate a decoded harness contribution manifest."""

    root = _mapping(document, "Harness contribution manifest")
    allowed_keys = {"$schema", "schema_version", "kind", "source", "contributions"}
    extra = sorted(set(root) - allowed_keys)
    if extra:
        raise HarnessInteropError(
            "interop.manifest_extra",
            f"Harness contribution manifest contains unsupported fields: {', '.join(extra)}.",
        )
    if root.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise HarnessInteropError("interop.schema_version", "Harness contribution schema_version must be 1.")
    if root.get("kind") != MANIFEST_KIND:
        raise HarnessInteropError("interop.kind_invalid", f"Harness contribution kind must be {MANIFEST_KIND!r}.")

    source = _mapping(root.get("source"), "Manifest source")
    source_extra = sorted(set(source) - {"repository", "commit_sha", "authority_paths"})
    if source_extra:
        raise HarnessInteropError(
            "interop.source_extra",
            f"Manifest source contains unsupported fields: {', '.join(source_extra)}.",
        )

    raw_contributions = root.get("contributions")
    if not isinstance(raw_contributions, list) or not raw_contributions:
        raise HarnessInteropError("interop.contributions_invalid", "Manifest contributions must be a non-empty array.")
    contributions = tuple(_contribution(item) for item in raw_contributions)
    identifiers = tuple(item.contribution_id for item in contributions)
    if len(set(identifiers)) != len(identifiers):
        raise HarnessInteropError("interop.contribution_duplicate", "Contribution ids must be unique.")

    return HarnessContributionManifest(
        source_repository=_repository(source.get("repository")),
        source_commit_sha=_commit_sha(source.get("commit_sha")),
        authority_paths=_string_list(source.get("authority_paths"), "Source authority paths", paths=True),
        contributions=contributions,
    )


def load_harness_contribution_manifest(path: Path) -> HarnessContributionManifest:
    """Load a harness contribution manifest from disk without network access."""

    resolved = path.expanduser().resolve()
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessInteropError("interop.manifest_missing", f"Manifest does not exist at {resolved}.") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessInteropError("interop.manifest_parse", f"Manifest could not be parsed: {exc}.") from exc
    return parse_harness_contribution_manifest(document)
