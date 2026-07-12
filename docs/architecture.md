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
observe -> classify -> select -> execute -> validate -> record -> transition
   ^                                                               |
   +---------------------------------------------------------------+
```

The loop continues only while policy, scope, and evidence permit it. Continuum stops with a structured blocker when human intent, unsafe access, novel reasoning, or missing proof prevents a safe transition.

## State ownership

### Committed product contracts

Repository identity, commands, safety boundaries, evidence requirements, schemas, decision records, and workflow definitions belong in version control.

### Local runtime state

Caches, temporary run records, worktree indexes, and local databases are ignored. They must not pollute feature branches or product history.

### Durable execution evidence

CI artifacts, checks, pull-request comments, and dedicated evidence stores may preserve execution history without forcing every runtime event into source control.

## Current implementation boundary

Version `0.1.0` implements deterministic inspection of `.continuum/repository.json`. The `doctor` command reads a repository contract without mutation or network access and emits either syntactic-English evidence or structured JSON. Agent dispatch, workflow scheduling, GitHub mutation, and cross-repository execution remain future work and must not be represented as implemented.
