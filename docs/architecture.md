# Continuum architecture

Continuum separates intent, durable repository state, deterministic orchestration, bounded agent reasoning, and environmental evidence.

## Actors

| Actor | Responsibility |
| --- | --- |
| Human | Intent, priorities, policy, and exceptions |
| Repository | Contracts, code, decisions, validators, and durable memory |
| Orchestrator | Observation, topology decisions, task/result gates, and transitions |
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

Caller-reported evidence is preserved but cannot authorize successful completion. Independent artifact verifiers remain future work. Workflow decisions are advisory and record `applied: false`.

## State ownership

Committed contracts, schemas, tests, policies, and decisions belong in Git. Caches, attachments, process handles, and run state remain local or external. CI artifacts and result packets may preserve durable evidence without polluting feature branches.

## Current implementation boundary

Version `0.4.0` implements read-only contract, Git, domain, topology, task, result, and transition decisions. It does not execute commands, mutate GitHub, verify referenced artifacts, attach to WezTerm, persist workflow state, or dispatch agents.
