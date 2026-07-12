# Continuum Agent Contract

## Repository identity

- Repository: `EndeavorEverlasting/Continuum`
- Default branch: `main`
- Product role: local repository orchestration and durable development-state control plane
- Current proof boundary: dependency-free contract inspection and bounded task-packet compilation from local Git evidence

## Operating loop

Every sprint follows this order:

1. Inspect repository, branch, pull-request, and worktree evidence.
2. Resolve owned scope and forbidden scope from durable contracts.
3. Compile a provider-neutral task packet before implementation begins.
4. Make the smallest bounded change that advances the sprint.
5. Run targeted tests, repository validation, compilation, and packaging checks.
6. Record changed files, command results, gaps, risks, and Git state.
7. Commit only after the evidence supports the completion claim.

## Canonical commands

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
python -m pip install --no-deps -e .
continuum doctor . --json
continuum task . \
  --owned "bounded sprint scope" \
  --forbidden "unrelated changes" \
  --json
```

## Safety boundaries

Agents must not:

- mutate another repository without explicit owned scope;
- add network behavior to contract or Git evidence inspection;
- begin a task without explicit owned and forbidden scope;
- claim autonomous orchestration that has not been exercised and recorded;
- commit credentials, secrets, local state, run caches, or generated evidence;
- weaken validators or replace real behavior with stubs merely to pass checks;
- rewrite unrelated files during a bounded sprint.

## Durable state

Committed product state belongs in source, schemas, tests, workflows, and documentation. Local execution state belongs under ignored `.continuum/cache/`, `.continuum/runs/`, or `.continuum/state/` paths. Durable external evidence may later be published through CI artifacts, checks, pull-request comments, or a dedicated evidence store.

Task packets are immutable inputs assembled from committed contracts, explicit scope, and read-only local Git evidence. They are not agent memory and do not authorize work beyond their declared boundaries.

## Completion evidence

A completion report names:

- every created or modified file;
- every validation command and its result;
- skipped checks and the exact command still required;
- known gaps and risks;
- commit SHA and push state;
- final `git status --short` output.
