"""Read-only repository contract inspection."""
from __future__ import annotations
from dataclasses import dataclass
import json, re
from pathlib import Path
from typing import Any

CONTRACT_RELATIVE_PATH = Path('.continuum/repository.json')
SUPPORTED_SCHEMA_VERSION = 1
STACKING = {'forbidden', 'explicit_only', 'allowed'}
SLUG = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    message: str

    def to_dict(self):
        return {'id': self.check_id, 'passed': self.passed, 'message': self.message}


@dataclass(frozen=True)
class InspectionReport:
    root: Path
    contract_path: Path
    checks: tuple[CheckResult, ...]

    @property
    def ok(self):
        return bool(self.checks) and all(c.passed for c in self.checks)

    def to_dict(self):
        passed = sum(c.passed for c in self.checks)
        return {
            'schema_version': 1,
            'command': 'doctor',
            'repository_root': str(self.root),
            'contract_path': str(self.contract_path),
            'status': 'ready' if self.ok else 'blocked',
            'summary': {
                'total': len(self.checks),
                'passed': passed,
                'failed': len(self.checks) - passed,
            },
            'checks': [c.to_dict() for c in self.checks],
        }

    def render_english(self):
        passed = sum(c.passed for c in self.checks)
        status = 'ready' if self.ok else 'blocked'
        lines = [
            f'Continuum inspected the repository at {self.root}.',
            f'Continuum evaluated the contract at {self.contract_path}.',
            f'Continuum completed {len(self.checks)} checks: {passed} passed and {len(self.checks) - passed} failed.',
            f'Continuum classified the repository as {status}.',
        ]
        lines += [
            f"{'PASS' if c.passed else 'FAIL'} [{c.check_id}]: {c.message}"
            for c in self.checks
        ]
        return '\n'.join(lines)


def _text(v):
    return isinstance(v, str) and bool(v.strip())


def _list(v, required=False):
    return isinstance(v, list) and (not required or bool(v)) and all(_text(x) for x in v)


def _map(v):
    return isinstance(v, dict) and bool(v) and all(_text(k) and _text(x) for k, x in v.items())


def _check(out, i, ok, good, bad):
    out.append(CheckResult(i, bool(ok), good if ok else bad))


def inspect_repository(root: Path) -> InspectionReport:
    root = root.expanduser().resolve()
    path = root / CONTRACT_RELATIVE_PATH
    out = []
    if not path.is_file():
        _check(out, 'contract.exists', False, 'contract exists', 'The repository contract does not exist.')
        return InspectionReport(root, path, tuple(out))
    _check(out, 'contract.exists', True, 'The repository contract exists.', '')
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _check(out, 'contract.parse', False, '', f'The repository contract could not be parsed: {exc}.')
        return InspectionReport(root, path, tuple(out))
    obj = isinstance(doc, dict)
    _check(out, 'contract.parse', obj, 'The repository contract is a JSON object.', 'The repository contract must be a JSON object.')
    if not obj:
        return InspectionReport(root, path, tuple(out))
    _check(out, 'contract.schema_version', doc.get('schema_version') == 1, 'The schema version is 1.', 'The schema version must be 1.')
    _check(out, 'contract.harness_version', _text(doc.get('harness_version')), 'The harness version is declared.', 'The harness version must be declared.')
    repo = doc.get('repository')
    ok = isinstance(repo, dict)
    _check(out, 'repository.object', ok, 'The repository section is valid.', 'The repository section must be an object.')
    repo = repo if ok else {}
    _check(out, 'repository.name', _text(repo.get('name')), 'The repository name is declared.', 'The repository name must be declared.')
    default = repo.get('default_branch')
    _check(out, 'repository.default_branch', _text(default), 'The default branch is declared.', 'The default branch must be declared.')
    branch = doc.get('branch_policy')
    ok = isinstance(branch, dict)
    _check(out, 'branch_policy.object', ok, 'The branch policy is valid.', 'The branch policy must be an object.')
    branch = branch if ok else {}
    _check(out, 'branch_policy.canonical_base', _text(branch.get('canonical_base')) and branch.get('canonical_base') == default, 'The canonical base matches the default branch.', 'The canonical base must match repository.default_branch.')
    _check(out, 'branch_policy.stacked_pull_requests', branch.get('stacked_pull_requests') in STACKING, 'The stacking policy is declared.', 'The stacking policy is invalid.')
    for key in ('merge_green_predecessors_before_next_sprint', 'require_clean_base', 'require_current_canonical_base'):
        _check(out, f'branch_policy.{key}', isinstance(branch.get(key), bool), f'{key} is boolean.', f'{key} must be boolean.')
    proof = doc.get('completion_proof')
    ok = isinstance(proof, dict)
    _check(out, 'completion_proof.object', ok, 'The completion proof is valid.', 'The completion proof must be an object.')
    proof = proof if ok else {}
    _check(out, 'completion_proof.provider', proof.get('provider') == 'github_actions', 'The provider is GitHub Actions.', 'The provider must be github_actions.')
    slug = proof.get('repository')
    slug_valid = isinstance(slug, str) and slug == slug.strip() and bool(SLUG.fullmatch(slug.strip()))
    _check(out, 'completion_proof.repository', slug_valid, 'The repository uses owner/name form.', 'The repository must use owner/name form.')
    _check(out, 'completion_proof.workflow', _text(proof.get('workflow')), 'The workflow is declared.', 'The workflow must be declared.')
    _check(out, 'completion_proof.event', proof.get('event') == 'push', 'The event is push.', 'The event must be push.')
    _check(out, 'completion_proof.required_conclusion', proof.get('required_conclusion') == 'success', 'The conclusion is success.', 'The conclusion must be success.')
    _check(out, 'commands.mapping', _map(doc.get('commands')), 'The command map is valid.', 'The command map must contain command strings.')
    bounds = doc.get('boundaries')
    ok = isinstance(bounds, dict)
    _check(out, 'boundaries.object', ok, 'The boundaries section is valid.', 'The boundaries section must be an object.')
    bounds = bounds if ok else {}
    _check(out, 'boundaries.protected_paths', _list(bounds.get('protected_paths')), 'The protected paths are valid.', 'The protected paths must be strings.')
    _check(out, 'boundaries.forbidden_operations', _list(bounds.get('forbidden_operations'), True), 'The forbidden operations are declared.', 'At least one forbidden operation is required.')
    evidence = doc.get('evidence')
    ok = isinstance(evidence, dict)
    _check(out, 'evidence.object', ok, 'The evidence section is valid.', 'The evidence section must be an object.')
    evidence = evidence if ok else {}
    _check(out, 'evidence.required', _list(evidence.get('required'), True), 'The required evidence is declared.', 'At least one evidence item is required.')
    if proof.get('provider') == 'github_actions':
        required_evidence = evidence.get('required') if isinstance(evidence.get('required'), list) else []
        has_github_actions = 'github_actions' in required_evidence
        _check(out, 'evidence.required.github_actions', has_github_actions, 'github_actions evidence is required when using GitHub Actions provider.', 'The required evidence must include github_actions when completion_proof.provider is github_actions.')
    return InspectionReport(root, path, tuple(out))
