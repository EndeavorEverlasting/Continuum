# Continuum

**A local orchestration engine that carries repository context, evidence, and workflow state across agents, sessions, and development sprints.**

Continuum moves repeatable software-development coordination out of a human's head and into versioned repository contracts, deterministic gates, and durable evidence. Humans retain intent and policy; replaceable agents receive bounded work.

## Control loop

```text
observe -> classify -> topology gate -> compile task + domain -> execute -> record result -> evidence gate -> transition
```

## Current proof boundary

Continuum `0.5.0` implements:

- repository-contract inspection;
- named execution-domain validation informed by [WezTerm](https://github.com/wezterm/wezterm);
- read-only Git evidence and provider-neutral task packets;
- caller-reported result packets that cannot authorize completion without independent verification;
- deterministic branch-topology decisions that prevent unnecessary stacked pull requests;
- read-only GitHub Actions completion proof bound to an exact repository, canonical branch, commit SHA, workflow, event, and successful conclusion;
- automatic `workflow_run` proof artifacts after canonical `main` CI completes.

It does not execute repository command maps, attach to terminals, apply workflow state, dispatch agents, or mutate GitHub. The GitHub Actions adapter performs read-only API queries or verifies a GitHub-owned `workflow_run` event.

## Branch topology

Every governed repository declares branch policy in `.continuum/repository.json`:

```json
{
  "branch_policy": {
    "canonical_base": "main",
    "stacked_pull_requests": "explicit_only",
    "merge_green_predecessors_before_next_sprint": true,
    "require_clean_base": true,
    "require_current_canonical_base": true
  }
}
```

The default flow is:

```text
green predecessor PR -> merge -> refresh main -> create next branch from main
```

A noncanonical base is blocked unless policy allows stacking or a bounded exception includes a reason. A green, mergeable predecessor must still merge first.

Evaluate a normalized snapshot without network access or mutation:

```bash
continuum topology branch-topology.json --repository . --json
```

## Automated CI completion proof

Repositories declare the exact GitHub Actions run that can provide canonical post-push proof:

```json
{
  "completion_proof": {
    "provider": "github_actions",
    "repository": "EndeavorEverlasting/Continuum",
    "workflow": "CI",
    "event": "push",
    "required_conclusion": "success"
  }
}
```

After a push, Continuum can poll GitHub directly and exit only when the exact workflow run is final:

```bash
continuum ci-proof . \
  --commit "$(git rev-parse HEAD)" \
  --wait-seconds 300 \
  --json
```

`GH_TOKEN` or `GITHUB_TOKEN` is used ephemerally when present and is never persisted or rendered. Public repositories can use GitHub's unauthenticated read-only endpoint subject to normal rate limits.

The `Completion Proof` workflow also runs automatically after `CI` completes on `main`. It verifies the GitHub-owned `workflow_run` payload, publishes a job summary, and uploads `completion-proof.json` as an immutable workflow artifact. A failed, cancelled, missing, pending, wrong-branch, wrong-commit, wrong-event, or wrong-workflow run cannot produce a passing proof.

## Task and result packets

```bash
continuum task . \
  --domain local-inspection \
  --owned "bounded sprint scope" \
  --forbidden "unrelated changes" \
  --json > task-packet.json
```

Caller-reported evidence is transport data, not proof. A reported successful result remains `unverified` and exits nonzero unless every required completion claim is independently verified:

```bash
continuum result task-packet.json \
  --outcome succeeded \
  --evidence validation_results=passed=artifacts/validation.json \
  --json
```

## Validation

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
python -m pip install --no-deps -e .
```

## Structure

```text
.continuum/                 Repository, branch, proof, and execution-domain contracts
.github/workflows/          CI and automatic completion-proof workflows
schemas/                    Machine-readable packet, proof, and decision contracts
src/continuum/              Deterministic inspection, verification, and decision code
tests/                      Executable contract behavior
docs/                       Architecture and prior-art decisions
AGENTS.md                    Agent operating contract
```

Continuum is available under the [MIT License](LICENSE).
