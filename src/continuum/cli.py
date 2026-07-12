"""Command-line interface for Continuum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .branch_topology import BranchTopologyError, evaluate_branch_topology, load_branch_policy, load_topology_snapshot
from .completion_gates import CompletionGateError, parse_evidence_argument
from .contracts import inspect_repository
from .result_packets import ResultPacketError, compile_result_packet, load_task_packet
from .task_packets import TaskPacketError, compile_task_packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="continuum", description="Inspect repositories and compile bounded orchestration evidence.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="Validate a repository's embedded Continuum contract.")
    doctor.add_argument("path", nargs="?", default=".")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    task = subcommands.add_parser("task", help="Compile a provider-neutral task packet from contract and Git evidence.")
    task.add_argument("path", nargs="?", default=".")
    task.add_argument("--owned", action="append", required=True)
    task.add_argument("--forbidden", action="append", required=True)
    task.add_argument("--domain")
    task.add_argument("--task-id")
    task.add_argument("--recent-commits", type=int, default=5)
    task.add_argument("--json", action="store_true", dest="as_json")

    topology = subcommands.add_parser("topology", help="Evaluate whether a proposed branch base is permitted by repository policy.")
    topology.add_argument("snapshot", help="Path to a normalized branch-topology snapshot.")
    topology.add_argument("--repository", default=".", help="Repository whose contract supplies branch policy.")
    topology.add_argument("--json", action="store_true", dest="as_json")

    result = subcommands.add_parser("result", help="Compile a result packet, conservative completion gate, and workflow decision.")
    result.add_argument("task_packet")
    result.add_argument("--outcome", required=True, choices=("succeeded", "blocked", "failed"))
    result.add_argument("--evidence", action="append", default=[])
    result.add_argument("--domain-availability", default="unverified", choices=("unverified",))
    result.add_argument("--observed-capability", action="append", default=[])
    result.add_argument("--domain-evidence")
    result.add_argument("--blocker-code")
    result.add_argument("--blocker-message")
    result.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _emit(payload: object, *, as_json: bool, english: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if as_json else english)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        report = inspect_repository(Path(args.path))
        _emit(report.to_dict(), as_json=args.as_json, english=report.render_english())
        return 0 if report.ok else 1
    if args.command == "task":
        try:
            packet = compile_task_packet(Path(args.path), owned_scope=args.owned, forbidden_scope=args.forbidden, domain_name=args.domain, task_id=args.task_id, recent_limit=args.recent_commits)
        except TaskPacketError as exc:
            _emit(exc.to_dict(), as_json=args.as_json, english=f"Continuum blocked task-packet compilation: {exc}")
            return 1
        _emit(packet.to_dict(), as_json=args.as_json, english=packet.render_english())
        return 0
    if args.command == "topology":
        try:
            policy = load_branch_policy(Path(args.repository))
            snapshot = load_topology_snapshot(Path(args.snapshot))
            decision = evaluate_branch_topology(policy, snapshot)
        except BranchTopologyError as exc:
            _emit(exc.to_dict(), as_json=args.as_json, english=f"Continuum blocked branch-topology evaluation: {exc}")
            return 1
        _emit(decision.to_dict(), as_json=args.as_json, english=decision.render_english())
        return 0 if decision.allowed else 1
    if args.command == "result":
        try:
            task_document = load_task_packet(Path(args.task_packet))
            evidence = tuple(parse_evidence_argument(item) for item in args.evidence)
            packet = compile_result_packet(task_document, outcome=args.outcome, evidence_records=evidence, domain_availability=args.domain_availability, observed_capabilities=args.observed_capability, domain_evidence_reference=args.domain_evidence, blocker_code=args.blocker_code, blocker_message=args.blocker_message)
        except (CompletionGateError, ResultPacketError) as exc:
            structured = exc.to_dict() if isinstance(exc, ResultPacketError) else ResultPacketError(exc.code, str(exc)).to_dict()
            _emit(structured, as_json=args.as_json, english=f"Continuum blocked result-packet compilation: {exc}")
            return 1
        _emit(packet.to_dict(), as_json=args.as_json, english=packet.render_english())
        return 0 if packet.status == "ready" else 1
    raise AssertionError(f"Unhandled command: {args.command}")
