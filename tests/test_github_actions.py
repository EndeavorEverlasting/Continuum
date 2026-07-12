from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.github_actions import (  # noqa: E402
    GitHubActionsError,
    GitHubActionsPolicy,
    evaluate_github_actions_runs,
    fetch_github_actions_proof,
    load_github_actions_policy,
    proof_from_workflow_run_event,
    resolve_github_token,
    wait_for_github_actions_proof,
)

SHA = "a" * 40
POLICY = GitHubActionsPolicy(
    repository="EndeavorEverlasting/Continuum",
    workflow="CI",
    event="push",
    required_conclusion="success",
    branch="main",
)


def run_document(
    *,
    run_id: int = 101,
    repository: str = "EndeavorEverlasting/Continuum",
    name: str = "CI",
    path: str = ".github/workflows/ci.yml",
    event: str = "push",
    status: str = "completed",
    conclusion: str | None = "success",
    branch: str = "main",
    sha: str = SHA,
    attempt: int = 1,
) -> dict[str, object]:
    return {
        "id": run_id,
        "repository": {"full_name": repository},
        "name": name,
        "path": path,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "head_branch": branch,
        "head_sha": sha,
        "html_url": f"https://github.com/EndeavorEverlasting/Continuum/actions/runs/{run_id}",
        "run_attempt": attempt,
    }


class GitHubActionsProofTests(unittest.TestCase):
    def test_loads_repository_declared_policy(self) -> None:
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
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".continuum").mkdir()
            (root / ".continuum" / "repository.json").write_text(json.dumps(contract), encoding="utf-8")
            policy = load_github_actions_policy(root)
        self.assertEqual(POLICY, policy)

    def test_rejects_noncanonical_completion_policy(self) -> None:
        contract = {
            "repository": {"name": "Continuum", "default_branch": "main"},
            "completion_proof": {
                "provider": "github_actions",
                "repository": "not-a-slug",
                "workflow": "CI",
                "event": "push",
                "required_conclusion": "success",
            },
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".continuum").mkdir()
            (root / ".continuum" / "repository.json").write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(GitHubActionsError) as raised:
                load_github_actions_policy(root)
        self.assertEqual("github_actions.repository_invalid", raised.exception.code)

    def test_workflow_run_event_produces_independent_passed_proof(self) -> None:
        proof = proof_from_workflow_run_event(POLICY, {"workflow_run": run_document()})
        payload = proof.to_dict()
        self.assertTrue(proof.passed)
        self.assertEqual("passed", payload["status"])
        self.assertEqual("github-workflow-run-event", payload["source"])
        self.assertEqual("passed", payload["evidence"]["status"])
        self.assertEqual(101, payload["run"]["id"])

    def test_failed_workflow_conclusion_blocks_proof(self) -> None:
        proof = proof_from_workflow_run_event(
            POLICY,
            {"workflow_run": run_document(conclusion="failure")},
        )
        payload = proof.to_dict()
        self.assertFalse(proof.passed)
        self.assertEqual("github_actions.run_failed", payload["blocker"]["code"])
        self.assertEqual("failed", payload["evidence"]["status"])

    def test_exact_identity_filter_rejects_wrong_branch_or_commit(self) -> None:
        proof = evaluate_github_actions_runs(
            POLICY,
            SHA,
            [
                run_document(branch="feature"),
                run_document(sha="b" * 40),
                run_document(repository="Other/Repository"),
            ],
            source="github-api",
        )
        self.assertEqual("github_actions.run_missing", proof.blocker["code"])

    def test_latest_attempt_controls_the_decision(self) -> None:
        proof = evaluate_github_actions_runs(
            POLICY,
            SHA,
            [
                run_document(run_id=100, attempt=1, conclusion="success"),
                run_document(run_id=102, attempt=2, conclusion="failure"),
            ],
            source="github-api",
        )
        self.assertFalse(proof.passed)
        self.assertEqual(102, proof.run.run_id)
        self.assertEqual("github_actions.run_failed", proof.blocker["code"])

    def test_api_fetch_uses_read_only_filters_and_does_not_render_token(self) -> None:
        captured: dict[str, object] = {}

        def fetch_json(url: str, headers: dict[str, str], timeout: float):
            captured.update(url=url, headers=headers, timeout=timeout)
            return {"workflow_runs": [run_document()]}

        proof = fetch_github_actions_proof(
            POLICY,
            SHA,
            token="secret-token",
            timeout_seconds=7,
            fetch_json=fetch_json,
        )
        self.assertTrue(proof.passed)
        self.assertIn("head_sha=" + SHA, captured["url"])
        self.assertIn("branch=main", captured["url"])
        self.assertIn("event=push", captured["url"])
        self.assertEqual("Bearer secret-token", captured["headers"]["Authorization"])
        self.assertNotIn("secret-token", json.dumps(proof.to_dict()))

    def test_wait_retries_missing_and_pending_until_success(self) -> None:
        responses = iter(
            [
                {"workflow_runs": []},
                {"workflow_runs": [run_document(status="in_progress", conclusion=None)]},
                {"workflow_runs": [run_document(status="completed", conclusion="success")]},
            ]
        )
        clock = [0.0]
        sleeps: list[float] = []

        def fetch_json(url: str, headers: dict[str, str], timeout: float):
            return next(responses)

        def monotonic() -> float:
            return clock[0]

        def sleeper(seconds: float) -> None:
            sleeps.append(seconds)
            clock[0] += seconds

        proof = wait_for_github_actions_proof(
            POLICY,
            SHA,
            wait_seconds=10,
            poll_seconds=1,
            fetch_json=fetch_json,
            monotonic=monotonic,
            sleeper=sleeper,
        )
        self.assertTrue(proof.passed)
        self.assertEqual([1, 1], sleeps)

    def test_wait_timeout_returns_structured_blocker(self) -> None:
        clock = [0.0]

        def fetch_json(url: str, headers: dict[str, str], timeout: float):
            return {"workflow_runs": []}

        def monotonic() -> float:
            return clock[0]

        def sleeper(seconds: float) -> None:
            clock[0] += seconds

        proof = wait_for_github_actions_proof(
            POLICY,
            SHA,
            wait_seconds=2,
            poll_seconds=1,
            fetch_json=fetch_json,
            monotonic=monotonic,
            sleeper=sleeper,
        )
        self.assertEqual("github_actions.wait_timeout", proof.blocker["code"])

    def test_token_resolution_prefers_gh_token(self) -> None:
        self.assertEqual("gh", resolve_github_token({"GH_TOKEN": "gh", "GITHUB_TOKEN": "actions"}))
        self.assertIsNone(resolve_github_token({}))


if __name__ == "__main__":
    unittest.main()
