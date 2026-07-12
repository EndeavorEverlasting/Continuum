"""Run Continuum's dependency-free repository validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.contracts import inspect_repository  # noqa: E402
from continuum.execution_domains import (  # noqa: E402
    ExecutionDomainError,
    load_execution_domains,
)
from continuum.task_packets import TaskPacketError, compile_task_packet  # noqa: E402

SCHEMA_PATHS = (
    ROOT / "schemas" / "repository.schema.json",
    ROOT / "schemas" / "execution-domains.schema.json",
    ROOT / "schemas" / "task-packet.schema.json",
)


def main() -> int:
    for schema_path in SCHEMA_PATHS:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"Continuum could not parse {schema_path}: {exc}.")
            return 1

        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            print(
                f"Continuum found an unsupported or missing JSON Schema dialect in {schema_path}."
            )
            return 1
        print(f"Continuum parsed the JSON Schema document at {schema_path}.")

    report = inspect_repository(ROOT)
    print(report.render_english())
    if not report.ok:
        return 1

    try:
        domain = load_execution_domains(ROOT).resolve()
    except ExecutionDomainError as exc:
        print(f"Continuum could not load its execution-domain registry: {exc}")
        return 1

    if (
        domain.name != "local-inspection"
        or domain.capabilities != ("inspect",)
        or domain.auto_start
    ):
        print("Continuum's default execution domain must remain inspection-only.")
        return 1

    try:
        packet = compile_task_packet(
            ROOT,
            owned_scope=["Continuum repository validation"],
            forbidden_scope=["network access", "cross-repository mutation"],
            domain_name=domain.name,
        )
    except TaskPacketError as exc:
        print(f"Continuum could not compile its validation task packet: {exc}")
        return 1

    payload = packet.to_dict()
    if (
        payload.get("status") != "ready"
        or payload.get("kind") != "continuum.task-packet"
        or payload.get("execution", {}).get("availability") != "unverified"
    ):
        print("Continuum compiled an invalid task-packet envelope.")
        return 1

    print(
        "Continuum compiled validation task packet "
        f"{packet.task_id} for unverified execution domain {domain.name}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
