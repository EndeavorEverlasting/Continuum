from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.cli import main  # noqa: E402
from continuum.contracts import inspect_repository  # noqa: E402


VALID_CONTRACT = {
    "schema_version": 1,
    "harness_version": "0.1.0",
    "repository": {
        "name": "Example",
        "default_branch": "main",
    },
    "commands": {
        "test": "python -m unittest",
    },
    "boundaries": {
        "protected_paths": [],
        "forbidden_operations": ["force_push"],
    },
    "evidence": {
        "required": ["validation_results"],
    },
}


def write_contract(root: Path, document: object) -> None:
    contract_dir = root / ".continuum"
    contract_dir.mkdir(parents=True)
    (contract_dir / "repository.json").write_text(
        json.dumps(document),
        encoding="utf-8",
    )


class ContractInspectionTests(unittest.TestCase):
    def test_valid_contract_is_ready(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)

            report = inspect_repository(root)

            self.assertTrue(report.ok)
            self.assertEqual("ready", report.to_dict()["status"])
            self.assertEqual(0, report.to_dict()["summary"]["failed"])

    def test_missing_contract_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            report = inspect_repository(Path(directory))

            self.assertFalse(report.ok)
            self.assertEqual("contract.exists", report.checks[0].check_id)
            self.assertFalse(report.checks[0].passed)

    def test_malformed_contract_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract_dir = root / ".continuum"
            contract_dir.mkdir()
            (contract_dir / "repository.json").write_text("{", encoding="utf-8")

            report = inspect_repository(root)

            self.assertFalse(report.ok)
            self.assertEqual("contract.parse", report.checks[-1].check_id)

    def test_missing_safety_boundary_is_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(json.dumps(VALID_CONTRACT))
            document["boundaries"]["forbidden_operations"] = []
            write_contract(root, document)

            report = inspect_repository(root)

            self.assertFalse(report.ok)
            failed_ids = {check.check_id for check in report.checks if not check.passed}
            self.assertIn("boundaries.forbidden_operations", failed_ids)

    def test_cli_emits_json_and_success_exit_code(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["doctor", str(root), "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("ready", payload["status"])
            self.assertEqual("doctor", payload["command"])

    def test_cli_fails_for_missing_contract(self) -> None:
        with TemporaryDirectory() as directory:
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["doctor", directory])

            self.assertEqual(1, exit_code)
            self.assertIn("classified the repository as blocked", output.getvalue())


if __name__ == "__main__":
    unittest.main()
