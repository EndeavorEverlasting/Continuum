# Harness contribution interoperability

Continuum and BlacksmithGuild are being used to test how a repository-specific app can donate reusable harness patterns to a repository-neutral orchestration control plane without erasing domain boundaries.

## First boundary

The first integration surface is `.continuum/harness-contributions.json`. It is a read-only, commit-pinned inventory of candidate capabilities. It does not import source code, mutate BlacksmithGuild, or claim that a documented pattern has already been implemented in Continuum.

Each contribution records:

- the exact donor commit and source paths;
- whether the capability is portable harness plumbing, a repository skill, or domain-specific behavior;
- whether the donor capability is merged, experimental, or deprecated;
- whether Continuum should absorb it into its harness, adapt it as a targeted skill, retain it as reference material, or reject it;
- the concrete capabilities and rationale for that disposition.

`src/continuum/harness_interop.py` rejects mutable source references, path traversal, duplicate identifiers, unknown fields, experimental adoption, and attempts to move domain-specific behavior into the Continuum harness.

## Authority chain

1. The donor repository remains authoritative for its source contracts, skills, and runtime behavior.
2. The pinned contribution manifest is an adoption proposal, not independent runtime proof.
3. Continuum may implement a contribution only in a later bounded sprint with its own tests, validators, and proof ceiling.
4. BlacksmithGuild-specific gameplay, launcher, campaign, and runtime behavior remains outside Continuum unless a portable cross-cutting concern is extracted explicitly.

## Initial candidates

The first inventory identifies three portable candidates from merged BlacksmithGuild work:

- harness-versus-skill maturity classification;
- repository-floor and worktree hygiene;
- common agent rules with targeted skill routing.

The operator terminal environment doctrine remains reference-only because Continuum should expose clean orchestration surfaces without owning personal terminal configuration or game-operator workflows.

## Validation

```bash
python -m unittest -v tests/test_harness_interop.py
python -m compileall -q src/continuum/harness_interop.py tests/test_harness_interop.py
```

Passing these checks provides contract and static-test proof only. It does not prove cross-repository runtime behavior or complete any future port.
