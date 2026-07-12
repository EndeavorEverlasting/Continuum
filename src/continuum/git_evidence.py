"""Read-only local Git evidence collection."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any


class GitEvidenceError(RuntimeError):
    """Raised when deterministic Git evidence cannot be collected."""


@dataclass(frozen=True)
class GitCommit:
    sha: str
    subject: str

    def to_dict(self) -> dict[str, str]:
        return {"sha": self.sha, "subject": self.subject}


@dataclass(frozen=True)
class GitEvidence:
    repository_root: Path
    branch: str | None
    head_sha: str
    status_entries: tuple[str, ...]
    recent_commits: tuple[GitCommit, ...]

    @property
    def detached(self) -> bool:
        return self.branch is None

    @property
    def dirty(self) -> bool:
        return bool(self.status_entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository_root": str(self.repository_root),
            "branch": self.branch,
            "detached": self.detached,
            "head_sha": self.head_sha,
            "dirty": self.dirty,
            "status_entries": list(self.status_entries),
            "recent_commits": [commit.to_dict() for commit in self.recent_commits],
        }


def _run_git(root: Path, *arguments: str, allow_failure: bool = False) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitEvidenceError("Git is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitEvidenceError("Git evidence collection timed out.") from exc

    if completed.returncode != 0 and not allow_failure:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Git error"
        raise GitEvidenceError(
            f"Git command {' '.join(arguments)} failed: {detail}."
        )
    return completed.stdout.rstrip("\n")


def collect_git_evidence(root: Path, *, recent_limit: int = 5) -> GitEvidence:
    """Collect branch, HEAD, status, and recent commits without network access."""

    if recent_limit < 1 or recent_limit > 50:
        raise ValueError("recent_limit must be between 1 and 50.")

    requested_root = root.expanduser().resolve()
    top_level = _run_git(requested_root, "rev-parse", "--show-toplevel")
    repository_root = Path(top_level).resolve()
    head_sha = _run_git(repository_root, "rev-parse", "HEAD").strip()

    branch_text = _run_git(
        repository_root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        allow_failure=True,
    ).strip()
    branch = branch_text or None

    status_text = _run_git(
        repository_root,
        "status",
        "--short",
        "--untracked-files=all",
    )
    status_entries = tuple(line for line in status_text.splitlines() if line)

    log_text = _run_git(
        repository_root,
        "log",
        f"-{recent_limit}",
        "--format=%H%x1f%s",
    )
    commits: list[GitCommit] = []
    for line in log_text.splitlines():
        sha, separator, subject = line.partition("\x1f")
        if not separator:
            raise GitEvidenceError("Git returned an unparseable commit record.")
        commits.append(GitCommit(sha=sha, subject=subject))

    return GitEvidence(
        repository_root=repository_root,
        branch=branch,
        head_sha=head_sha,
        status_entries=status_entries,
        recent_commits=tuple(commits),
    )
