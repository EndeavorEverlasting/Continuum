from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.cli import main  # noqa: E402
from continuum.git_evidence import collect_git_evidence  # noqa: E402
from continuum.task_packets import TaskPacketError, compile_task_packet  # noqa: E402
from test_contracts import VALID_CONTRACT, write_contract  # noqa: E402


def run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialize_repository(root: Path) -> str:
    run_git(root, "init")
    run_git(root, "branch", "-M", "main")
    run_git(root, "config", "user.name", "Continuum Tests")
    run_git(root, "config", "user.email", "continuum-tests@example.invalid")
    write_contract(root, VALID_CONTRACT)
    (root / "tracked.txt").write_text("initial\n", encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "test: initialize repository")
    return run_git(root, "rev-parse", "HEAD")


class GitEvidenceTests(unittest.TestCase):
    def test_collects_clean_local_repository_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            expected_sha = initialize_repository(root)

            evidence = collect_git_evidence(root)

            self.assertEqual(root.resolve(), evidence.repository_root)
            self.assertEqual("main", evidence.branch)
            self.assertEqual(expected_sha, evidence.head_sha)
            self.assertFalse(evidence.dirty)
            self.assertEqual(1, len(evidence.recent_commits))

    def test_collects_dirty_status_without_modifying_repository(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")

            evidence = collect_git_evidence(root)

            self.assertTrue(evidence.dirty)
            self.assertIn(" M tracked.txt", evidence.status_entries)
            self.assertEqual("changed\n", (root / "tracked.txt").read_text(encoding="utf-8"))


class TaskPacketTests(unittest.TestCase):
    def test_compiles_deterministic_provider_neutral_packet(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            expected_sha = initialize_repository(root)

            first = compile_task_packet(
                root,
                owned_scope=["task packet compiler", "local Git evidence"],
                forbidden_scope=["network access", "cross-repository mutation"],
            )
            second = compile_task_packet(
                root,
                owned_scope=["task packet compiler", "local Git evidence"],
                forbidden_scope=["network access", "cross-repository mutation"],
            )
            payload = first.to_dict()

            self.assertEqual(first.task_id, second.task_id)
            self.assertEqual("ready", payload["status"])
            self.assertEqual("continuum.task-packet", payload["kind"])
            self.assertEqual(expected_sha, payload["git"]["head_sha"])
            self.assertEqual("main", payload["git"]["branch"])
            self.assertEqual(
                ["task packet compiler", "local Git evidence"],
                payload["scope"]["owned"],
            )
            self.assertIn("test", payload["contract"]["commands"])
            self.assertEqual(
                ["validation_results"],
                payload["contract"]["required_evidence"],
            )

    def test_rejects_duplicate_scope_entries(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)

            with self.assertRaises(TaskPacketError) as raised:
                compile_task_packet(
                    root,
                    owned_scope=["same", "same"],
                    forbidden_scope=["network access"],
                )

            self.assertEqual("scope.owned_duplicate", raised.exception.code)

    def test_blocks_non_git_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)

            with self.assertRaises(TaskPacketError) as raised:
                compile_task_packet(
                    root,
                    owned_scope=["task packet compiler"],
                    forbidden_scope=["network access"],
                )

            self.assertEqual("git.unavailable", raised.exception.code)

    def test_blocks_contract_below_git_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            nested = root / "nested"
            nested.mkdir()
            write_contract(nested, VALID_CONTRACT)

            with self.assertRaises(TaskPacketError) as raised:
                compile_task_packet(
                    nested,
                    owned_scope=["nested contract"],
                    forbidden_scope=["parent mutation"],
                )

            self.assertEqual("git.root_mismatch", raised.exception.code)

    def test_cli_emits_ready_json_packet(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "task",
                        str(root),
                        "--owned",
                        "task packet compiler",
                        "--forbidden",
                        "network access",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertEqual("ready", payload["status"])
            self.assertTrue(payload["task_id"].startswith("task-"))

    def test_cli_emits_structured_blocker(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_contract(root, VALID_CONTRACT)
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "task",
                        str(root),
                        "--owned",
                        "task packet compiler",
                        "--forbidden",
                        "network access",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertEqual("git.unavailable", payload["blocker"]["code"])


if __name__ == "__main__":
    unittest.main()
