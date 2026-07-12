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
observe -> classify -> compile task + domain -> execute -> validate -> record -> transition
   ^                                                                               |
   +-------------------------------------------------------------------------------+
```

The loop continues only while policy, scope, domain capability, and evidence permit it. Continuum stops with a structured blocker when human intent, unsafe access, novel reasoning, an undeclared execution target, or missing proof prevents a safe transition.

## Execution-domain boundary

An execution domain identifies a bounded runtime target independently from the task, agent provider, and user interface. The repository declares domains in `.continuum/execution-domains.json`.

| Field | Meaning |
| --- | --- |
| `name` | Stable repository-local identifier selected by a task. |
| `transport` | Topology such as local, Unix socket, SSH, TLS, WSL, serial, or a custom adapter. |
| `lifecycle` | Whether Continuum may eventually manage the domain or must treat it as externally owned. |
| `auto_start` | Explicit policy for future adapters; never inferred from transport. |
| `capabilities` | Operations an adapter may eventually expose, such as inspect, spawn, attach, detach, read, or write. |
| `availability` | Runtime evidence. Task compilation currently fixes this to `unverified` and performs no connection or process probe. |

A task cannot authorize behavior that its domain does not declare. A declared capability is still not proof that the behavior succeeded. Future adapters must emit observed state and results separately.

### WezTerm prior art

WezTerm demonstrates the value of this boundary at production scale:

- multiplexing is organized into named domains rather than implicit shells;
- local, Unix-socket, SSH, TLS, WSL, serial, and other transports sit behind domain behavior;
- attach, detach, spawnability, state, and auto-start decisions are explicit;
- the CLI acts as a client of an existing GUI or multiplexer server rather than owning durable terminal state;
- structured CLI output is available independently from the interactive terminal surface.

Continuum adopts those separation principles, not WezTerm's pane/window model or protocol implementation. The current code only validates domain declarations and includes the selected declaration in a task packet. It does not start WezTerm, connect to a socket, spawn a process, or report attached/detached runtime state. See [`prior-art/wezterm.md`](prior-art/wezterm.md).

## Task-packet boundary

A task packet is a provider-neutral, immutable input assembled before an agent is invoked. Version `0.2.0` includes:

- repository identity and harness version from `.continuum/repository.json`;
- explicit owned and forbidden scope supplied by the governor or upstream workflow;
- a named execution-domain declaration from `.continuum/execution-domains.json`;
- local Git root, branch or detached state, HEAD SHA, short status, and recent commits;
- repository commands, protected paths, forbidden operations, and required evidence;
- a deterministic task ID derived from repository state, scope, and selected domain.

Task compilation is read-only and performs no network calls or runtime probes. A missing contract, invalid scope, unknown domain, invalid lifecycle policy, non-Git directory, or contract/Git-root mismatch produces a machine-readable blocker and a nonzero exit code.

## State ownership

### Committed product contracts

Repository identity, commands, execution domains, safety boundaries, evidence requirements, schemas, decision records, and workflow definitions belong in version control.

### Local runtime state

Caches, temporary run records, worktree indexes, local databases, terminal attachments, and process handles are runtime state. They must not pollute feature branches or product history.

### Durable execution evidence

CI artifacts, checks, pull-request comments, result packets, and dedicated evidence stores may preserve execution history without forcing every runtime event into source control.

## Current implementation boundary

Version `0.2.0` implements deterministic repository-contract inspection, execution-domain registry validation, and bounded task-packet compilation from local Git evidence. It does not execute repository commands, attach or detach a domain, dispatch an agent, write result packets, advance workflow states, mutate GitHub, or operate across repositories. Those capabilities remain future work and must not be represented as implemented.
