# Continuum architecture

Continuum separates durable intent from repeatable execution so that a repository does not depend on one chat session, one model, or one human carrying operational context.

## Actors

| Actor | Responsibility | Boundary |
| --- | --- | --- |
| Human | Supplies intent, priorities, policy, and exceptions. | The human is not the workflow engine. |
| Repository | Stores product code, contracts, decisions, validators, and durable state. | The repository is not an undocumented pile of implementation details. |
| Orchestrator | Observes state, selects permitted work, invokes tools, validates results, and records transitions. | The orchestrator does not invent product intent. |
| Agent | Performs bounded reasoning or implementation when deterministic tooling is insufficient. | The agent is replaceable and is not the sole keeper of context. |
| Environment | Produces objective signals from Git, CI, runtimes, artifacts, and external systems. | Environmental output must be normalized before it controls a transition. |

## Control loop

```text
observe -> classify -> compile task -> execute -> validate -> record -> transition
   ^                                                                      |
   +----------------------------------------------------------------------+
```

The loop continues only while policy, scope, and evidence permit it. Continuum stops with a structured blocker when human intent, unsafe access, novel reasoning, or missing proof prevents a safe transition.

## Task packet boundary

A task packet is a provider-neutral, immutable input assembled before an agent is invoked. Version `0.2.0` includes:

- repository identity and harness version from `.continuum/repository.json`;
- explicit owned and forbidden scope supplied by the governor or upstream workflow;
- local Git root, branch or detached state, HEAD SHA, short status, and recent commits;
- repository commands, protected paths, forbidden operations, and required evidence;
- a deterministic task ID derived from repository state and scope.

Task compilation is read-only and performs no network calls. A missing contract, invalid scope, non-Git directory, or contract/Git-root mismatch produces a machine-readable blocker and a nonzero exit code.

## State ownership

### Committed product contracts

Repository identity, commands, safety boundaries, evidence requirements, schemas, decision records, and workflow definitions belong in version control.

### Local runtime state

Caches, temporary run records, worktree indexes, and local databases are ignored. They must not pollute feature branches or product history.

### Durable execution evidence

CI artifacts, checks, pull-request comments, and dedicated evidence stores may preserve execution history without forcing every runtime event into source control.

## Current implementation boundary

Version `0.2.0` implements deterministic repository-contract inspection and bounded task-packet compilation from local Git evidence. It does not execute repository commands, dispatch an agent, write result packets, advance workflow states, mutate GitHub, or operate across repositories. Those capabilities remain future work and must not be represented as implemented.
