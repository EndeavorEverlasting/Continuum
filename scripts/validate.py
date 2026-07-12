"""Run Continuum's dependency-free repository validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.completion_gates import EvidenceRecord  # noqa: E402
from continuum.contracts import inspect_repository  # noqa: E402
from continuum.execution_domains import (  # noqa: E402
    ExecutionDomainError,
    load_execution_domains,
)
from continuum.result_packets import ResultPacketError, compile_result_packet  # noqa: E402
from continuum.task_packets import TaskPacketError, compile_task_packet  # noqa: E402

SCHEMA_PATHS = (
    ROOT / "schemas" / "repository.schema.json",
    ROOT / "schemas" / "execution-domains.schema.json",
    ROOT / "schemas" / "task-packet.schema.json",
    ROOT / "schemas" / "result-packet.schema.json",
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
        task_packet = compile_task_packet(
            ROOT,
            owned_scope=["Continuum repository validation"],
            forbidden_scope=["network access", "cross-repository mutation"],
            domain_name=domain.name,
        )
    except TaskPacketError as exc:
        print(f"Continuum could not compile its validation task packet: {exc}")
        return 1

    task_payload = task_packet.to_dict()
    if (
        task_payload.get("status") != "ready"
        or task_payload.get("kind") != "continuum.task-packet"
        or task_payload.get("execution", {}).get("availability") != "unverified"
    ):
        print("Continuum compiled an invalid task-packet envelope.")
        return 1

    evidence = tuple(
        EvidenceRecord(name=name, status="passed", reference=f"self-validation:{name}")
        for name in task_packet.contract.required_evidence
    )
    try:
        result_packet = compile_result_packet(
            task_payload,
            outcome="succeeded",
            evidence_records=evidence,
            domain_availability="unverified",
        )
    except ResultPacketError as exc:
        print(f"Continuum could not compile its validation result packet: {exc}")
        return 1

    result_payload = result_packet.to_dict()
    if (
        result_payload.get("status") != "blocked"
        or result_payload.get("kind") != "continuum.result-packet"
        or result_payload.get("completion_gate", {}).get("status") != "unverified"
        or result_payload.get("transition", {}).get("decision") != "blocked"
        or result_payload.get("transition", {}).get("to") != "completed"
        or result_payload.get("transition", {}).get("applied") is not False
    ):
        print("Continuum compiled an unsafe result-packet envelope.")
        return 1

    print(
        "Continuum compiled validation task packet "
        f"{task_packet.task_id} and result packet {result_packet.result_id}."
    )
    print("Continuum correctly blocked completion because evidence was not independently verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
