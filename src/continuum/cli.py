"""Command-line interface for Continuum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import inspect_repository
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

    raise AssertionError(f"Unhandled command: {args.command}")
