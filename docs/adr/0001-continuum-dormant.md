# ADR 0001 — Continuum dormant; AgentSwitchboard is the active control plane

- Status: Accepted
- Date: 2026-09-12

## Context

Continuum was created as a local orchestration engine for repository context, evidence, workflow state, branch topology, task/result packets, and future agent execution. Since then, AgentSwitchboard has become the active execution and coordination control plane for agent/model selection, bootstrap/runtime resolution, child-agent dispatch, repository coordination, intervention, validation, and evidence-driven completion.

Keeping both products active would create duplicate orchestration ownership and unnecessary maintenance.

## Decision

Continuum is **dormant** and retained as a preserved reference implementation. `EndeavorEverlasting/AgentSwitchboard` is the **active control plane**.

Continuum does not own active:

- agent or model selection;
- process launch, bootstrap, or runtime resolution;
- prompt routing;
- Git/repository workflow control;
- polling or intervention;
- completion/validation gates;
- ordinary repository work-state tracking;
- child-agent dispatch or provider adapters.

Existing Continuum `0.4.0` code, schemas, tests, and documentation remain available as historical/reference material. They are not an active roadmap.

## Dormant development policy

While dormant:

- feature development is not allowed;
- runtime/orchestration expansion is not allowed;
- new integrations, adapters, execution domains, and orchestration capabilities are not allowed;
- open feature PRs that conflict with this decision should be closed rather than carried as latent roadmap work;
- only security fixes, dependency fixes, archival maintenance, and documentation corrections are allowed.

The machine-readable owner is `.continuum/lifecycle.json`, validated by `scripts/validate.py` and CI.

## Reactivation

There is **no automatic reactivation gate** and no durable-state trigger that can reactivate Continuum.

`reactivation_allowed` is false. Any future attempt to make Continuum active again requires a new, explicit architecture decision by the repository owner that first changes the lifecycle contract. Prior ideas about durable cross-process workflow state are retained only as historical context; they do not create queued work or an activation condition.

## Consequences

- AgentSwitchboard remains the single active control-plane target.
- Continuum stays available for reference without competing for implementation attention.
- Existing behavior may still be validated, but validation does not promote the repository back into the active stack.
- New orchestration capabilities belong in AgentSwitchboard unless a future explicit architecture decision says otherwise.
