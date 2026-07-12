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
    "harness_version": "0.4.0",
    "repository": {"name": "Example", "default_branch": "main"},
    "branch_policy": {
        "canonical_base": "main",
        "stacked_pull_requests": "explicit_only",
        "merge_green_predecessors_before_next_sprint": True,
        "require_clean_base": True,
        "require_current_canonical_base": True,
    },
    "commands": {"test": "python -m unittest"},
    "boundaries": {"protected_paths": [], "forbidden_operations": ["force_push"]},
    "evidence": {"required": ["validation_results"]},
}


def write_contract(root: Path, document: object) -> None:
    contract_dir = root / ".continuum"
    contract_dir.mkdir(parents=True)
    (contract_dir / "repository.json").write_text(json.dumps(document), encoding="utf-8")


class ContractInspectionTests(unittest.TestCase):
    def test_valid_contract_is_ready(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)
            report = inspect_repository(root)
            self.assertTrue(report.ok)
            self.assertEqual("ready", report.to_dict()["status"])

    def test_missing_contract_is_blocked(self):
        with TemporaryDirectory() as directory:
            report = inspect_repository(Path(directory))
            self.assertFalse(report.ok)
            self.assertEqual("contract.exists", report.checks[0].check_id)

    def test_malformed_contract_is_blocked(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract_dir = root / ".continuum"
            contract_dir.mkdir()
            (contract_dir / "repository.json").write_text("{", encoding="utf-8")
            report = inspect_repository(root)
            self.assertEqual("contract.parse", report.checks[-1].check_id)

    def test_missing_safety_boundary_is_blocked(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(json.dumps(VALID_CONTRACT))
            document["boundaries"]["forbidden_operations"] = []
            write_contract(root, document)
            failed = {check.check_id for check in inspect_repository(root).checks if not check.passed}
            self.assertIn("boundaries.forbidden_operations", failed)

    def test_branch_policy_must_match_default_branch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(json.dumps(VALID_CONTRACT))
            document["branch_policy"]["canonical_base"] = "develop"
            write_contract(root, document)
            failed = {check.check_id for check in inspect_repository(root).checks if not check.passed}
            self.assertIn("branch_policy.canonical_base", failed)

    def test_branch_policy_requires_explicit_stacking_mode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(json.dumps(VALID_CONTRACT))
            document["branch_policy"]["stacked_pull_requests"] = "sometimes"
            write_contract(root, document)
            failed = {check.check_id for check in inspect_repository(root).checks if not check.passed}
            self.assertIn("branch_policy.stacked_pull_requests", failed)

    def test_cli_emits_json_and_success_exit_code(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["doctor", str(root), "--json"])
            self.assertEqual(0, exit_code)
            self.assertEqual("ready", json.loads(output.getvalue())["status"])

    def test_cli_fails_for_missing_contract(self):
        with TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["doctor", directory])
            self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
