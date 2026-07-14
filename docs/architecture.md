# Continuum architecture

Continuum separates intent, durable repository state, deterministic orchestration, bounded agent reasoning, and environmental evidence.

## Actors

| Actor | Responsibility |
| --- | --- |
| Human | Intent, priorities, policy, and exceptions |
| Repository | Contracts, code, decisions, validators, and durable memory |
| Orchestrator | Observation, topology decisions, task/result gates, verification, and transitions |
| Agent | Replaceable bounded reasoning and implementation |
| Environment | Git, CI, runtime, artifact, and service signals |

## Controlled loop

```text
observe -> topology gate -> task packet -> execution -> result packet -> evidence gate -> transition
```

### Branch-topology boundary

Branch selection occurs before task execution. The repository declares a canonical base, stacking policy, merge-first rule, and clean/current-base requirements. A normalized environment snapshot is evaluated without network access or mutation. See [`branch-topology.md`](branch-topology.md).

### Execution-domain boundary

Execution targets are named domains with explicit transports, lifecycle, auto-start policy, and capabilities. This separation is informed by WezTerm's multiplexer architecture. A declaration is not runtime proof.

### Evidence boundary

Caller-reported evidence is preserved but cannot authorize successful completion. Independent verifiers must bind a claim to provider-owned state and emit a durable reference.

The first independent verifier is the read-only GitHub Actions completion-proof adapter. It binds repository, branch, commit, workflow, event, run attempt, status, and conclusion. It can collect state through GitHub's API or verify the GitHub-owned `workflow_run` event used by the automatic completion-proof workflow. See [`completion-proof.md`](completion-proof.md).

Result packets remain conservative: a GitHub Actions proof verifies only the CI claim it names. Other caller-reported evidence remains unverified until an appropriate verifier exists.

### Provider-adapter boundary

Provider adapters are explicit and capability-limited. The GitHub Actions adapter may issue read-only workflow-run requests and read ephemeral token environment variables. It cannot create, rerun, cancel, merge, retarget, delete, or otherwise mutate GitHub state.

## State ownership

Committed contracts, schemas, tests, policies, and decisions belong in Git. Caches, attachments, process handles, and run state remain local or external. CI artifacts and result packets may preserve durable evidence without polluting feature branches.

## Current implementation boundary

Version `0.5.0` implements read-only contract, Git, domain, topology, task, result, transition, and GitHub Actions completion-proof decisions. It does not execute repository command maps, mutate GitHub, attach to WezTerm, persist workflow state, or dispatch agents.
