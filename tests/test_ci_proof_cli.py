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

SHA = "a" * 40


def write_repository(root: Path, *, conclusion: str = "success") -> Path:
    contract_dir = root / ".continuum"
    contract_dir.mkdir(parents=True)
    contract = {
        "repository": {"name": "Continuum", "default_branch": "main"},
        "completion_proof": {
            "provider": "github_actions",
            "repository": "EndeavorEverlasting/Continuum",
            "workflow": "CI",
            "event": "push",
            "required_conclusion": "success",
        },
    }
    (contract_dir / "repository.json").write_text(json.dumps(contract), encoding="utf-8")
    event = {
        "workflow_run": {
            "id": 101,
            "repository": {"full_name": "EndeavorEverlasting/Continuum"},
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "event": "push",
            "status": "completed",
            "conclusion": conclusion,
            "head_branch": "main",
            "head_sha": SHA,
            "html_url": "https://github.com/EndeavorEverlasting/Continuum/actions/runs/101",
            "run_attempt": 1,
        }
    }
    event_path = root / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    return event_path


class CiProofCliTests(unittest.TestCase):
    def test_event_file_passes_and_emits_proof_json(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = write_repository(root)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ci-proof", str(root), "--event-file", str(event_path), "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertEqual("github-workflow-run-event", payload["source"])

    def test_failed_event_returns_nonzero_and_structured_blocker(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = write_repository(root, conclusion="failure")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ci-proof", str(root), "--event-file", str(event_path), "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("github_actions.run_failed", payload["blocker"]["code"])

    def test_event_file_rejects_waiting(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = write_repository(root)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([
                    "ci-proof",
                    str(root),
                    "--event-file",
                    str(event_path),
                    "--wait-seconds",
                    "10",
                    "--json",
                ])
        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("github_actions.wait_conflict", payload["blocker"]["code"])


if __name__ == "__main__":
    unittest.main()
