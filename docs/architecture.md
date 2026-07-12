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
observe -> classify -> compile task + domain -> execute -> record result -> gate -> transition
   ^                                                                                 |
   +---------------------------------------------------------------------------------+
```

The loop continues only while policy, scope, domain capability, evidence, and transition rules permit it. Continuum stops with a structured blocker when human intent, unsafe access, an undeclared execution target, missing proof, or a failed completion gate prevents a safe transition.

## Execution-domain boundary

An execution domain identifies a bounded runtime target independently from the task, agent provider, and user interface. The repository declares domains in `.continuum/execution-domains.json`.

| Field | Meaning |
| --- | --- |
| `name` | Stable repository-local identifier selected by a task. |
| `transport` | Topology such as local, Unix socket, SSH, TLS, WSL, serial, or a custom adapter. |
| `lifecycle` | Whether Continuum may eventually manage the domain or must treat it as externally owned. |
| `auto_start` | Explicit policy for future adapters; never inferred from transport. |
| `capabilities` | Operations an adapter may eventually expose, such as inspect, spawn, attach, detach, read, or write. |
| `availability` | Runtime evidence. Task compilation fixes this to `unverified`; result packets may carry caller-reported observations. |

A task cannot authorize behavior that its domain does not declare. A declared capability is still not proof that behavior succeeded. A result packet may record observed or unavailable state only with an evidence reference, and observed capabilities must be a subset of the task declaration.

### WezTerm prior art

WezTerm demonstrates the value of this boundary at production scale:

- multiplexing is organized into named domains rather than implicit shells;
- local, Unix-socket, SSH, TLS, WSL, serial, and other transports sit behind domain behavior;
- attach, detach, spawnability, state, and auto-start decisions are explicit;
- the CLI acts as a client of an existing GUI or multiplexer server rather than owning durable terminal state;
- structured CLI output is available independently from the interactive terminal surface.

Continuum adopts those separation principles, not WezTerm's pane/window model or protocol implementation. The current code does not start WezTerm, connect to a socket, spawn a process, or independently observe attached/detached state. See [`prior-art/wezterm.md`](prior-art/wezterm.md).

## Task-packet boundary

A task packet is a provider-neutral, immutable input assembled before an agent is invoked. Version `0.3.0` includes:

- repository identity and harness version from `.continuum/repository.json`;
- explicit owned and forbidden scope supplied by the governor or upstream workflow;
- a named execution-domain declaration from `.continuum/execution-domains.json`;
- local Git root, branch or detached state, HEAD SHA, short status, and recent commits;
- repository commands, protected paths, forbidden operations, and required evidence;
- a deterministic task ID derived from repository state, scope, and selected domain.

Task compilation is read-only and performs no network calls or runtime probes.

## Result-packet boundary

A result packet is an immutable decision input assembled after work is reported. It is tied to one task ID and contains:

- caller-reported evidence records, each with a required name, status, and durable reference;
- a deterministic completion gate over the task's required evidence names;
- a caller-reported domain observation and optional observed capabilities;
- a structured blocker for blocked or failed outcomes;
- a deterministic transition decision.

Continuum does not read or verify referenced artifacts yet. The completion gate therefore proves structural completeness of the report, not truth of the underlying artifact. Evidence source is explicitly `caller-reported`.

## Completion gates

For a `succeeded` outcome, every required evidence record must be present and `passed`. Failed, skipped, or missing evidence blocks the completion decision. Unknown evidence names and duplicate records are rejected to prevent typo-driven false confidence.

For `blocked` or `failed` outcomes, a structured blocker is mandatory. Completion evidence is marked `not_applicable`, and the workflow may move to the blocked terminal decision.

## Workflow transitions

Version `0.3.0` models two result-driven decisions:

| Current state | Outcome | Gate | Decision |
| --- | --- | --- | --- |
| `ready` | `succeeded` | `passed` | allow `completed` |
| `ready` | `succeeded` | blocked | block `completed` |
| `ready` | `blocked` or `failed` | not applicable | allow `blocked` |

Every result packet records `applied: false`. Continuum can decide whether a transition is permitted, but it does not yet persist or mutate workflow state.

## State ownership

### Committed product contracts

Repository identity, commands, execution domains, safety boundaries, evidence requirements, schemas, decision records, and workflow definitions belong in version control.

### Local runtime state

Caches, temporary run records, worktree indexes, local databases, terminal attachments, process handles, and applied workflow state are runtime data. They must not pollute feature branches or product history.

### Durable execution evidence

CI artifacts, checks, pull-request comments, task packets, result packets, and dedicated evidence stores may preserve execution history without forcing every runtime event into source control.

## Current implementation boundary

Version `0.3.0` implements deterministic repository-contract inspection, execution-domain registry validation, task-packet compilation, result-packet compilation, structural completion gates, caller-reported domain observations, and non-mutating workflow-transition decisions. It does not execute repository commands, verify referenced artifact contents, attach or detach a domain, apply workflow state, dispatch an agent, mutate GitHub, or operate across repositories.
