# GitHub Actions completion proof

Continuum must not leave canonical CI verification as a human copy-and-paste command. The completion-proof adapter converts GitHub-owned workflow state into a structured, reproducible artifact.

## Trust boundary

A passing proof is bound to all of the following values:

- repository slug;
- canonical branch;
- exact commit SHA;
- configured workflow name or path;
- `push` event;
- `completed` workflow status;
- `success` conclusion;
- latest matching run attempt.

A successful run for another branch, another commit, another event, or another workflow is ignored. A previous successful attempt cannot mask a newer failed rerun.

## Collection paths

### Read-only API polling

```bash
continuum ci-proof . --commit <sha> --wait-seconds 300 --json
```

The command calls GitHub's workflow-runs endpoint with commit, branch, and event filters, then independently rechecks every returned field. It polls only missing or non-final states. Final failure is returned immediately.

Credentials are optional for public repositories. When present, `GH_TOKEN` takes precedence over `GITHUB_TOKEN`. Tokens are read from the environment, sent only in the authorization header, and never written into proof output.

### Automatic workflow-run attestation

`.github/workflows/completion-proof.yml` is triggered after `CI` completes. It accepts only a `push` run for `main`, checks out the exact head SHA, verifies the GitHub-owned event payload through the same library, and uploads `completion-proof.json`.

The workflow always attempts to publish the artifact and summary. Its final enforcement step fails when the proof is blocked, so an unsuccessful CI run cannot look complete.

## Output contract

Proof documents conform to `schemas/github-actions-proof.schema.json`. They contain:

- deterministic proof identity;
- repository, branch, and commit identity;
- required workflow policy;
- normalized workflow-run fields;
- independently sourced `github_actions` evidence when a final run exists;
- a structured blocker for missing, pending, failed, malformed, transport, or timeout states.

No branch, pull request, workflow, commit, or repository state is mutated by the adapter.
