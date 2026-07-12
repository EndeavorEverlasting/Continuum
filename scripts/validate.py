"""Run Continuum's dependency-free repository validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.contracts import inspect_repository  # noqa: E402


def main() -> int:
    schema_path = ROOT / "schemas" / "repository.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Continuum could not parse {schema_path}: {exc}.")
        return 1

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        print("Continuum found an unsupported or missing JSON Schema dialect.")
        return 1

    report = inspect_repository(ROOT)
    print(report.render_english())
    print(f"Continuum parsed the JSON Schema document at {schema_path}.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
