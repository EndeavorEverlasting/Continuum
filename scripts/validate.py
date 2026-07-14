"""Run Continuum's repository validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.branch_topology import BranchTopologyError, evaluate_branch_topology, load_branch_policy, parse_topology_snapshot  # noqa: E402
from continuum.completion_gates import EvidenceRecord  # noqa: E402
from continuum.contracts import inspect_repository  # noqa: E402
from continuum.execution_domains import ExecutionDomainError, load_execution_domains  # noqa: E402
from continuum.github_actions import GitHubActionsError, load_github_actions_policy, proof_from_workflow_run_event  # noqa: E402
from continuum.result_packets import ResultPacketError, compile_result_packet  # noqa: E402
from continuum.task_packets import TaskPacketError, compile_task_packet  # noqa: E402

SCHEMA_PATHS = (
    ROOT / "schemas" / "repository.schema.json",
    ROOT / "schemas" / "execution-domains.schema.json",
    ROOT / "schemas" / "task-packet.schema.json",
    ROOT / "schemas" / "result-packet.schema.json",
    ROOT / "schemas" / "branch-topology-snapshot.schema.json",
    ROOT / "schemas" / "branch-topology-decision.schema.json",
    ROOT / "schemas" / "github-actions-proof.schema.json",
)


def main() -> int:
    for schema_path in SCHEMA_PATHS:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"Continuum could not parse {schema_path}: {exc}.")
            return 1
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            print(f"Continuum found an unsupported or missing JSON Schema dialect in {schema_path}.")
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
    if domain.name != "local-inspection" or domain.capabilities != ("inspect",) or domain.auto_start:
        print("Continuum's default execution domain must remain inspection-only.")
        return 1

    try:
        task_packet = compile_task_packet(ROOT, owned_scope=["Continuum repository validation"], forbidden_scope=["network access", "cross-repository mutation"], domain_name=domain.name)
    except TaskPacketError as exc:
        print(f"Continuum could not compile its validation task packet: {exc}")
        return 1
    task_payload = task_packet.to_dict()
    if task_payload.get("contract", {}).get("branch_policy", {}).get("canonical_base") != "main":
        print("Continuum omitted branch policy from its task packet.")
        return 1
    if task_payload.get("contract", {}).get("completion_proof", {}).get("workflow") != "CI":
        print("Continuum omitted completion-proof policy from its task packet.")
        return 1

    evidence = tuple(EvidenceRecord(name=name, status="passed", reference=f"self-validation:{name}") for name in task_packet.contract.required_evidence)
    try:
        result_packet = compile_result_packet(task_payload, outcome="succeeded", evidence_records=evidence, domain_availability="unverified")
    except ResultPacketError as exc:
        print(f"Continuum could not compile its validation result packet: {exc}")
        return 1
    result_payload = result_packet.to_dict()
    if result_payload.get("completion_gate", {}).get("status") != "unverified" or result_payload.get("transition", {}).get("decision") != "blocked":
        print("Continuum compiled an unsafe result-packet envelope.")
        return 1

    try:
        policy = load_branch_policy(ROOT)
        snapshot = parse_topology_snapshot({
            "$schema": "schemas/branch-topology-snapshot.schema.json",
            "schema_version": 1,
            "kind": "continuum.branch-topology-snapshot",
            "canonical_branch": {"name": policy.canonical_base, "head_sha": task_packet.git.head_sha},
            "proposed_base": {"name": policy.canonical_base, "head_sha": task_packet.git.head_sha, "dirty": False},
            "stacking_exception": {"allowed": False, "reason": None},
            "open_pull_requests": [],
        })
        topology = evaluate_branch_topology(policy, snapshot)
    except BranchTopologyError as exc:
        print(f"Continuum could not evaluate its branch topology: {exc}")
        return 1
    if not topology.allowed or topology.decision != "create_branch_from_canonical":
        print("Continuum did not permit its clean current canonical base.")
        return 1

    try:
        ci_policy = load_github_actions_policy(ROOT)
        ci_proof = proof_from_workflow_run_event(
            ci_policy,
            {
                "workflow_run": {
                    "id": 1,
                    "repository": {"full_name": "EndeavorEverlasting/Continuum"},
                    "name": "CI",
                    "path": ".github/workflows/ci.yml",
                    "event": "push",
                    "status": "completed",
                    "conclusion": "success",
                    "head_branch": "main",
                    "head_sha": task_packet.git.head_sha,
                    "html_url": "https://github.com/EndeavorEverlasting/Continuum/actions/runs/1",
                    "run_attempt": 1,
                }
            },
        )
    except GitHubActionsError as exc:
        print(f"Continuum could not verify its GitHub Actions proof contract: {exc}")
        return 1
    if not ci_proof.passed or ci_proof.evidence is None or ci_proof.evidence.get("source") != "github-workflow-run-event":
        print("Continuum did not compile independent GitHub Actions completion proof.")
        return 1

    try:
        import jsonschema
    except ModuleNotFoundError:
        print("Continuum validation requires the optional validation dependencies. Install them with: python -m pip install -e '.[validation]'.")
        return 1

    proof_schema = json.loads((ROOT / "schemas" / "github-actions-proof.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(ci_proof.to_dict(), proof_schema)
    except jsonschema.ValidationError as exc:
        print(f"Continuum compiled a completion proof that violates its schema: {exc.message}")
        return 1

    print(f"Continuum compiled validation task packet {task_packet.task_id} and result packet {result_packet.result_id}.")
    print(f"Continuum compiled independent GitHub Actions proof {ci_proof.proof_id}.")
    print("Continuum correctly blocked completion because caller-reported evidence was not independently verified.")
    print("Continuum permitted branch creation only from the clean, current canonical base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
