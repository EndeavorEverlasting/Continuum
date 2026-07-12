from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.github_actions import (  # noqa: E402
    GitHubActionsError,
    GitHubActionsPolicy,
    evaluate_github_actions_runs,
    fetch_github_actions_proof,
    proof_from_workflow_run_event,
)

SHA = "a" * 40
POLICY = GitHubActionsPolicy(
    repository="EndeavorEverlasting/Continuum",
    workflow="CI",
    event="push",
    required_conclusion="success",
    branch="main",
)


def run_document(*, attempt: int = 1, conclusion: str = "success") -> dict[str, object]:
    return {
        "id": 102,
        "repository": {"full_name": "EndeavorEverlasting/Continuum"},
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "status": "completed",
        "conclusion": conclusion,
        "head_branch": "main",
        "head_sha": SHA,
        "html_url": "https://github.com/EndeavorEverlasting/Continuum/actions/runs/102",
        "run_attempt": attempt,
    }


class GitHubActionsSecurityTests(unittest.TestCase):
    def test_authenticated_fetch_rejects_untrusted_host_before_transport(self) -> None:
        called = False

        def fetch_json(url: str, headers: dict[str, str], timeout: float):
            nonlocal called
            called = True
            return {"workflow_runs": [run_document()]}

        with self.assertRaises(GitHubActionsError) as raised:
            fetch_github_actions_proof(
                POLICY,
                SHA,
                token="secret-token",
                api_url="https://attacker.example",
                fetch_json=fetch_json,
            )
        self.assertEqual("github_actions.api_url_untrusted", raised.exception.code)
        self.assertFalse(called)

    def test_fetch_rejects_non_https_api_url(self) -> None:
        with self.assertRaises(GitHubActionsError) as raised:
            fetch_github_actions_proof(
                POLICY,
                SHA,
                api_url="http://api.github.com",
                fetch_json=lambda *_: {"workflow_runs": [run_document()]},
            )
        self.assertEqual("github_actions.api_url_invalid", raised.exception.code)

    def test_unauthenticated_fetch_allows_https_enterprise_base(self) -> None:
        captured: dict[str, object] = {}

        def fetch_json(url: str, headers: dict[str, str], timeout: float):
            captured.update(url=url, headers=headers, timeout=timeout)
            return {"workflow_runs": [run_document()]}

        proof = fetch_github_actions_proof(
            POLICY,
            SHA,
            api_url="https://github.example/api/v3/",
            fetch_json=fetch_json,
        )
        self.assertTrue(proof.passed)
        self.assertTrue(str(captured["url"]).startswith("https://github.example/api/v3/repos/"))
        self.assertNotIn("Authorization", captured["headers"])

    def test_workflow_event_rejects_missing_or_nonpositive_attempt(self) -> None:
        missing = run_document()
        del missing["run_attempt"]
        for document in (missing, run_document(attempt=0), run_document(attempt=-1)):
            with self.subTest(document=document):
                with self.assertRaises(GitHubActionsError) as raised:
                    proof_from_workflow_run_event(POLICY, {"workflow_run": document})
                self.assertEqual("github_actions.run_invalid", raised.exception.code)

    def test_latest_attempt_wins_when_run_id_is_unchanged(self) -> None:
        proof = evaluate_github_actions_runs(
            POLICY,
            SHA,
            [
                run_document(attempt=1, conclusion="success"),
                run_document(attempt=2, conclusion="failure"),
            ],
            source="github-api",
        )
        self.assertFalse(proof.passed)
        self.assertEqual(102, proof.run.run_id)
        self.assertEqual(2, proof.run.run_attempt)
        self.assertEqual("github_actions.run_failed", proof.blocker["code"])


if __name__ == "__main__":
    unittest.main()
