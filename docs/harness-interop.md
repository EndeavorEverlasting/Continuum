# Harness contribution interoperability

> **Dormant override:** Continuum no longer absorbs new harness capabilities. This document and `.continuum/harness-contributions.json` are preserved reference material only while `.continuum/lifecycle.json` has `status: dormant`.

The original experiment used Continuum and BlacksmithGuild to test how a repository-specific app could donate reusable harness patterns to a repository-neutral orchestration layer without erasing domain boundaries. AgentSwitchboard now owns the active control-plane/harness role, so no new contribution may be implemented in Continuum while dormant.

## Preserved boundary

The existing integration surface is `.continuum/harness-contributions.json`. It is a read-only, commit-pinned inventory of historical candidate capabilities. It does not import source code, mutate donor repositories, authorize implementation, or create roadmap work.

Each contribution records:

- the exact donor commit and source paths;
- whether the capability was portable harness plumbing, a repository skill, or domain-specific behavior;
- whether the donor capability was merged, experimental, or deprecated;
- the historical disposition considered for Continuum;
- the capabilities and rationale for that disposition.

`src/continuum/harness_interop.py` remains preserved validation code. Passing its tests proves the historical manifest is coherent; it does not authorize adoption.

## Authority chain

1. Donor repositories remain authoritative for their source contracts, skills, and runtime behavior.
2. The pinned contribution manifest is historical/reference metadata, not runtime proof or queued implementation work.
3. Continuum does not absorb, adapt, or implement contributions while dormant.
4. AgentSwitchboard is the active control plane for new orchestration/harness capabilities.
5. Domain-specific donor behavior remains with the donor unless separately factored into the active owner.

## Historical candidates

The existing inventory retains prior candidates for reference, including harness-versus-skill maturity classification, repository-floor/worktree hygiene, and common agent rules with targeted skill routing.

Those entries do not constitute a backlog.

## Validation

```bash
python -m unittest -v tests/test_harness_interop.py
python -m compileall -q src/continuum/harness_interop.py tests/test_harness_interop.py
```

Passing these checks provides contract/static reference proof only. It does not reactivate Continuum or prove cross-repository runtime behavior.
