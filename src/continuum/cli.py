"""Command-line interface for Continuum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .completion_gates import CompletionGateError, parse_evidence_argument
from .contracts import inspect_repository
from .result_packets import ResultPacketError, compile_result_packet, load_task_packet
from .task_packets import TaskPacketError, compile_task_packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuum",
        description="Inspect repositories and compile bounded orchestration evidence.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser(
        "doctor",
        help="Validate a repository's embedded Continuum contract.",
    )
    doctor.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to inspect. The default is the current directory.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON evidence.",
    )

    task = subcommands.add_parser(
        "task",
        help="Compile a provider-neutral task packet from contract and Git evidence.",
    )
    task.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to inspect. The default is the current directory.",
    )
    task.add_argument(
        "--owned",
        action="append",
        required=True,
        help="One owned scope entry. Repeat the option for multiple entries.",
    )
    task.add_argument(
        "--forbidden",
        action="append",
        required=True,
        help="One forbidden scope entry. Repeat the option for multiple entries.",
    )
    task.add_argument(
        "--domain",
        help=(
            "Named execution domain from .continuum/execution-domains.json. "
            "The registry default is used when omitted."
        ),
    )
    task.add_argument(
        "--task-id",
        help="Optional caller-supplied task identifier.",
    )
    task.add_argument(
        "--recent-commits",
        type=int,
        default=5,
        help="Number of recent local commits to include, from 1 through 50.",
    )
    task.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the machine-readable task packet.",
    )

    result = subcommands.add_parser(
        "result",
        help="Compile a result packet, conservative completion gate, and workflow decision.",
    )
    result.add_argument(
        "task_packet",
        help="Path to a previously compiled Continuum task-packet JSON file.",
    )
    result.add_argument(
        "--outcome",
        required=True,
        choices=("succeeded", "blocked", "failed"),
        help="Reported task outcome.",
    )
    result.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="NAME=STATUS=REFERENCE",
        help=(
            "Caller-reported required evidence. STATUS is passed, failed, or skipped. "
            "Reported passes remain unverified until an independent verifier exists."
        ),
    )
    result.add_argument(
        "--domain-availability",
        default="unverified",
        choices=("unverified",),
        help="Execution-domain availability. Only unverified is accepted until an adapter verifier exists.",
    )
    result.add_argument(
        "--observed-capability",
        action="append",
        default=[],
        help="Reserved for a future independently verified domain adapter.",
    )
    result.add_argument(
        "--domain-evidence",
        help="Reserved for a future independently verified domain adapter.",
    )
    result.add_argument(
        "--blocker-code",
        help="Required structured blocker code for blocked or failed outcomes.",
    )
    result.add_argument(
        "--blocker-message",
        help="Required blocker explanation for blocked or failed outcomes.",
    )
    result.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the machine-readable result packet.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "doctor":
        report = inspect_repository(Path(args.path))
        if args.as_json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            print(report.render_english())
        return 0 if report.ok else 1

    if args.command == "task":
        try:
            packet = compile_task_packet(
                Path(args.path),
                owned_scope=args.owned,
                forbidden_scope=args.forbidden,
                domain_name=args.domain,
                task_id=args.task_id,
                recent_limit=args.recent_commits,
            )
        except TaskPacketError as exc:
            if args.as_json:
                print(json.dumps(exc.to_dict(), indent=2, sort_keys=True))
            else:
                print(f"Continuum blocked task-packet compilation: {exc}")
            return 1

        if args.as_json:
            print(json.dumps(packet.to_dict(), indent=2, sort_keys=True))
        else:
            print(packet.render_english())
        return 0

    if args.command == "result":
        try:
            task_document = load_task_packet(Path(args.task_packet))
            evidence = tuple(parse_evidence_argument(item) for item in args.evidence)
            packet = compile_result_packet(
                task_document,
                outcome=args.outcome,
                evidence_records=evidence,
                domain_availability=args.domain_availability,
                observed_capabilities=args.observed_capability,
                domain_evidence_reference=args.domain_evidence,
                blocker_code=args.blocker_code,
                blocker_message=args.blocker_message,
            )
        except (CompletionGateError, ResultPacketError) as exc:
            structured = (
                exc.to_dict()
                if isinstance(exc, ResultPacketError)
                else ResultPacketError(exc.code, str(exc)).to_dict()
            )
            if args.as_json:
                print(json.dumps(structured, indent=2, sort_keys=True))
            else:
                print(f"Continuum blocked result-packet compilation: {exc}")
            return 1

        if args.as_json:
            print(json.dumps(packet.to_dict(), indent=2, sort_keys=True))
        else:
            print(packet.render_english())
        return 0 if packet.status == "ready" else 1

    raise AssertionError(f"Unhandled command: {args.command}")
