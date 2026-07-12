"""Execution-domain contracts for bounded runtime targeting.

The domain boundary is conceptually informed by WezTerm's multiplexer domains:
callers select a named domain with explicit lifecycle and capabilities rather
than treating an arbitrary shell as the orchestration interface.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

EXECUTION_DOMAINS_RELATIVE_PATH = Path(".continuum/execution-domains.json")
SUPPORTED_EXECUTION_DOMAINS_SCHEMA_VERSION = 1
ALLOWED_TRANSPORTS = frozenset({"local", "unix", "ssh", "tls", "wsl", "serial", "custom"})
ALLOWED_LIFECYCLES = frozenset({"external", "managed"})
ALLOWED_CAPABILITIES = frozenset({"inspect", "spawn", "attach", "detach", "read", "write"})
_REGISTRY_KEYS = frozenset({"$schema", "schema_version", "default_domain", "domains"})
_DOMAIN_KEYS = frozenset({"transport", "lifecycle", "auto_start", "capabilities"})


class ExecutionDomainError(RuntimeError):
    """A structured blocker raised for an invalid execution-domain registry."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ExecutionDomain:
    """One declared execution target without a runtime availability claim."""

    name: str
    transport: str
    lifecycle: str
    auto_start: bool
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "transport": self.transport,
            "lifecycle": self.lifecycle,
            "auto_start": self.auto_start,
            "availability": "unverified",
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class ExecutionDomainRegistry:
    """Validated repository-local registry of named execution domains."""

    root: Path
    path: Path
    default_domain: str
    domains: Mapping[str, ExecutionDomain]

    def resolve(self, name: str | None = None) -> ExecutionDomain:
        selected = self.default_domain if name is None else name.strip()
        if not selected:
            raise ExecutionDomainError(
                "execution_domain.name_empty",
                "The execution-domain name must not be empty.",
            )
        try:
            return self.domains[selected]
        except KeyError as exc:
            available = ", ".join(sorted(self.domains))
            raise ExecutionDomainError(
                "execution_domain.unknown",
                f"Execution domain {selected!r} is not declared. Available domains: {available}.",
            ) from exc


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_domain(name: str, value: Any) -> ExecutionDomain:
    if not _nonempty_string(name) or name != name.strip():
        raise ExecutionDomainError(
            "execution_domain.invalid_name",
            "Execution-domain names must be non-empty strings without surrounding whitespace.",
        )
    if not isinstance(value, dict):
        raise ExecutionDomainError(
            "execution_domain.invalid_definition",
            f"Execution domain {name!r} must be a JSON object.",
        )

    unknown_keys = sorted(set(value) - _DOMAIN_KEYS)
    if unknown_keys:
        raise ExecutionDomainError(
            "execution_domain.unknown_field",
            f"Execution domain {name!r} contains unknown fields: {', '.join(unknown_keys)}.",
        )

    transport = value.get("transport")
    if transport not in ALLOWED_TRANSPORTS:
        raise ExecutionDomainError(
            "execution_domain.invalid_transport",
            f"Execution domain {name!r} has unsupported transport {transport!r}.",
        )

    lifecycle = value.get("lifecycle")
    if lifecycle not in ALLOWED_LIFECYCLES:
        raise ExecutionDomainError(
            "execution_domain.invalid_lifecycle",
            f"Execution domain {name!r} has unsupported lifecycle {lifecycle!r}.",
        )

    auto_start = value.get("auto_start")
    if not isinstance(auto_start, bool):
        raise ExecutionDomainError(
            "execution_domain.invalid_auto_start",
            f"Execution domain {name!r} must declare auto_start as a boolean.",
        )
    if lifecycle == "external" and auto_start:
        raise ExecutionDomainError(
            "execution_domain.lifecycle_conflict",
            f"Execution domain {name!r} cannot auto-start when its lifecycle is external.",
        )

    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ExecutionDomainError(
            "execution_domain.invalid_capabilities",
            f"Execution domain {name!r} must declare at least one capability.",
        )
    if not all(_nonempty_string(item) for item in capabilities):
        raise ExecutionDomainError(
            "execution_domain.invalid_capabilities",
            f"Execution domain {name!r} capabilities must be non-empty strings.",
        )
    if len(set(capabilities)) != len(capabilities):
        raise ExecutionDomainError(
            "execution_domain.duplicate_capability",
            f"Execution domain {name!r} declares duplicate capabilities.",
        )
    unsupported = sorted(set(capabilities) - ALLOWED_CAPABILITIES)
    if unsupported:
        raise ExecutionDomainError(
            "execution_domain.unsupported_capability",
            f"Execution domain {name!r} declares unsupported capabilities: {', '.join(unsupported)}.",
        )

    return ExecutionDomain(
        name=name,
        transport=transport,
        lifecycle=lifecycle,
        auto_start=auto_start,
        capabilities=tuple(sorted(capabilities)),
    )


def load_execution_domains(root: Path) -> ExecutionDomainRegistry:
    """Load and validate the repository-local execution-domain registry."""

    resolved_root = root.expanduser().resolve()
    path = resolved_root / EXECUTION_DOMAINS_RELATIVE_PATH
    if not path.is_file():
        raise ExecutionDomainError(
            "execution_domain.contract_missing",
            f"The execution-domain registry does not exist at {path}.",
        )

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionDomainError(
            "execution_domain.contract_parse",
            f"The execution-domain registry could not be parsed: {exc}.",
        ) from exc

    if not isinstance(document, dict):
        raise ExecutionDomainError(
            "execution_domain.contract_type",
            "The execution-domain registry must be a JSON object.",
        )

    unknown_registry_keys = sorted(set(document) - _REGISTRY_KEYS)
    if unknown_registry_keys:
        raise ExecutionDomainError(
            "execution_domain.contract_unknown_field",
            (
                "The execution-domain registry contains unknown fields: "
                f"{', '.join(unknown_registry_keys)}."
            ),
        )

    if document.get("schema_version") != SUPPORTED_EXECUTION_DOMAINS_SCHEMA_VERSION:
        raise ExecutionDomainError(
            "execution_domain.schema_version",
            (
                "The execution-domain schema version must be "
                f"{SUPPORTED_EXECUTION_DOMAINS_SCHEMA_VERSION}."
            ),
        )

    default_domain = document.get("default_domain")
    if not _nonempty_string(default_domain) or default_domain != default_domain.strip():
        raise ExecutionDomainError(
            "execution_domain.default_missing",
            "The execution-domain registry must declare a trimmed default_domain.",
        )

    raw_domains = document.get("domains")
    if not isinstance(raw_domains, dict) or not raw_domains:
        raise ExecutionDomainError(
            "execution_domain.domains_missing",
            "The execution-domain registry must declare at least one domain.",
        )

    domains = {name: _parse_domain(name, value) for name, value in raw_domains.items()}
    if default_domain not in domains:
        raise ExecutionDomainError(
            "execution_domain.default_unknown",
            f"The default execution domain {default_domain!r} is not declared.",
        )

    return ExecutionDomainRegistry(
        root=resolved_root,
        path=path,
        default_domain=default_domain,
        domains=MappingProxyType(dict(sorted(domains.items()))),
    )
