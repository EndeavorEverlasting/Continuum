# Continuum architecture

## Current status

Continuum is **dormant** and retained as a preserved reference implementation. `EndeavorEverlasting/AgentSwitchboard` is the active orchestration/control plane.

The authoritative lifecycle contract is `.continuum/lifecycle.json`; the accepted decision is `docs/adr/0001-continuum-dormant.md`.

No Continuum component is part of the active control plane while `reactivation_allowed` is false.

## Preserved architecture

Continuum historically separated intent, durable repository state, deterministic orchestration, bounded agent reasoning, and environmental evidence.

| Historical actor | Preserved responsibility |
| --- | --- |
| Human | Intent, priorities, policy, and exceptions |
| Repository | Contracts, code, decisions, validators, and durable memory |
| Orchestrator | Observation, topology decisions, task/result gates, and transitions |
| Agent | Replaceable bounded reasoning and implementation |
| Environment | Git, CI, runtime, artifact, and service signals |

Historical controlled loop:

```text
observe -> topology gate -> task packet -> execution -> result packet -> evidence gate -> transition
```

This loop is reference material, not an active runtime ownership model.

### Branch-topology boundary

The preserved implementation evaluates canonical-base, stacking, clean-base, and current-base rules without network access or mutation. See [`branch-topology.md`](branch-topology.md).

### Execution-domain boundary

Execution targets are represented as named domains with explicit transports, lifecycle, auto-start policy, and capabilities. These contracts remain preserved reference material; no new domain or runtime integration is authorized while dormant.

### Evidence boundary

Caller-reported evidence is preserved but cannot authorize successful completion. Existing evidence-gate behavior remains reference/test material and does not compete with AgentSwitchboard's active evidence and completion system.

## State ownership

Committed Continuum contracts, schemas, tests, policies, and decisions remain in Git. Caches, attachments, process handles, and run state remain local or external.

The lifecycle decision itself is repository state and is enforced by `scripts/validate.py` and CI. Historical PRs or implementation ideas cannot override it.

## Dormant boundary

Version `0.4.0` remains the preserved implementation floor. It does not execute commands, mutate GitHub, attach to terminals, dispatch agents, or own active orchestration.

No automatic reactivation condition exists. Any future active role requires a new explicit architecture decision that first changes `.continuum/lifecycle.json`.
