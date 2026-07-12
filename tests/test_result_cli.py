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
from test_result_packets import TASK_PACKET  # noqa: E402


class ResultCliTests(unittest.TestCase):
    def test_cli_blocks_caller_reported_success(self) -> None:
        with TemporaryDirectory() as directory:
            task_path = Path(directory) / "task.json"
            task_path.write_text(json.dumps(TASK_PACKET), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "result",
                        str(task_path),
                        "--outcome",
                        "succeeded",
                        "--evidence",
                        "commit_sha=passed=abc123",
                        "--evidence",
                        "validation_results=passed=artifacts/validation.json",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertEqual("unverified", payload["completion_gate"]["status"])

    def test_cli_returns_nonzero_for_missing_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            task_path = Path(directory) / "task.json"
            task_path.write_text(json.dumps(TASK_PACKET), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "result",
                        str(task_path),
                        "--outcome",
                        "succeeded",
                        "--evidence",
                        "commit_sha=passed=abc123",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual(["validation_results"], payload["completion_gate"]["missing"])


if __name__ == "__main__":
    unittest.main()
