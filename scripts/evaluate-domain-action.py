"""Evaluate a provider-neutral execution-domain action without applying it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.domain_lifecycle import (  # noqa: E402
    DomainLifecycleError,
    evaluate_domain_action,
    load_domain_snapshot,
)
from continuum.execution_domains import (  # noqa: E402
    ExecutionDomainError,
    load_execution_domains,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate attach, detach, or spawn for a declared execution domain."
    )
    parser.add_argument("snapshot", help="Path to an execution-domain snapshot JSON file.")
    parser.add_argument("--repository", default=".")
    parser.add_argument("--action", required=True, choices=("attach", "detach", "spawn"))
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _emit(payload: object, *, as_json: bool, english: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if as_json else english)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        registry = load_execution_domains(Path(args.repository))
        snapshot = load_domain_snapshot(Path(args.snapshot))
        domain = registry.resolve(snapshot.domain)
        decision = evaluate_domain_action(domain, snapshot, args.action)
    except (ExecutionDomainError, DomainLifecycleError) as exc:
        payload = exc.to_dict() if hasattr(exc, "to_dict") else {
            "status": "blocked",
            "blocker": {"code": exc.code, "message": str(exc)},
        }
        _emit(
            payload,
            as_json=args.as_json,
            english=f"Continuum blocked execution-domain action evaluation: {exc}",
        )
        return 1

    _emit(
        decision.to_dict(),
        as_json=args.as_json,
        english=decision.render_english(),
    )
    return 0 if decision.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
