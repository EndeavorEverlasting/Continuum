"""Command-line interface for Continuum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import inspect_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuum",
        description="Inspect repository contracts and emit durable evidence.",
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

    raise AssertionError(f"Unhandled command: {args.command}")
