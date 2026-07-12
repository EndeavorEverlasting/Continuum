from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.execution_domains import (  # noqa: E402
    ExecutionDomainError,
    load_execution_domains,
)

VALID_EXECUTION_DOMAINS = {
    "schema_version": 1,
    "default_domain": "local-inspection",
    "domains": {
        "local-inspection": {
            "transport": "local",
            "lifecycle": "external",
            "auto_start": False,
            "capabilities": ["inspect"],
        }
    },
}


def write_execution_domains(
    root: Path,
    document: object = VALID_EXECUTION_DOMAINS,
) -> None:
    contract_dir = root / ".continuum"
    contract_dir.mkdir(parents=True, exist_ok=True)
    (contract_dir / "execution-domains.json").write_text(
        json.dumps(document),
        encoding="utf-8",
    )


class ExecutionDomainTests(unittest.TestCase):
    def test_loads_default_domain_without_runtime_claim(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_execution_domains(root)

            domain = load_execution_domains(root).resolve()

            self.assertEqual("local-inspection", domain.name)
            self.assertEqual(["inspect"], domain.to_dict()["capabilities"])
            self.assertEqual("unverified", domain.to_dict()["availability"])

    def test_missing_registry_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            with self.assertRaises(ExecutionDomainError) as raised:
                load_execution_domains(Path(directory))

            self.assertEqual(
                "execution_domain.contract_missing",
                raised.exception.code,
            )

    def test_external_domain_cannot_auto_start(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(json.dumps(VALID_EXECUTION_DOMAINS))
            document["domains"]["local-inspection"]["auto_start"] = True
            write_execution_domains(root, document)

            with self.assertRaises(ExecutionDomainError) as raised:
                load_execution_domains(root)

            self.assertEqual(
                "execution_domain.lifecycle_conflict",
                raised.exception.code,
            )

    def test_unknown_domain_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_execution_domains(root)
            registry = load_execution_domains(root)

            with self.assertRaises(ExecutionDomainError) as raised:
                registry.resolve("missing")

            self.assertEqual("execution_domain.unknown", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
