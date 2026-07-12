# Continuum

**A local orchestration engine that carries repository context, evidence, and workflow state across agents, sessions, and development sprints.**

Continuum is intended to remove the human from repetitive software-development coordination without removing the human from intent. A repository carries its own operating contracts. Deterministic tooling performs inspection and validation. Replaceable agents receive bounded work only when reasoning is actually required.

## The model

Continuum treats software development as a controlled loop among five actors:

- **Human:** intent, priorities, policy, and exceptions.
- **Repository:** durable memory, contracts, code, tests, and decisions.
- **Orchestrator:** state observation, task selection, execution, validation, and transition.
- **Agent:** bounded reasoning and implementation.
- **Environment:** Git, CI, runtime, artifact, and service signals.

```text
observe -> classify -> compile task + domain -> execute -> record result -> gate -> transition
```

The repository and its evidence carry continuity. A chat session or model does not.

## Current proof boundary

Continuum `0.3.0` provides four executable foundations:

- dependency-free validation of an embedded `.continuum/repository.json` contract;
- validation and resolution of named execution domains from `.continuum/execution-domains.json`;
- bounded task-packet compilation from those contracts and read-only local Git evidence;
- immutable result-packet compilation with conservative completion gates and explicit workflow-transition decisions.

A task packet captures repository identity, scope, Git state, proof requirements, and a named execution domain. A result packet binds reported evidence and outcome back to that task ID. Caller-reported evidence can be recorded, but it cannot authorize completion. Until an independent verifier exists, an otherwise complete reported-success result remains `unverified`, returns a nonzero exit code, and blocks the `ready -> completed` transition.

Continuum does **not** yet execute commands, verify referenced artifact contents, independently observe domain state, attach to terminals, apply workflow state, dispatch agents, mutate GitHub, or operate across repositories. Every transition is emitted with `applied: false`.

## Quick start

Continuum requires Python 3.11 or newer.

```bash
git clone https://github.com/EndeavorEverlasting/Continuum.git
cd Continuum
python -m pip install --no-deps -e .
continuum doctor . --json
```

Compile a bounded task packet against the repository's inspection-only domain:

```bash
continuum task . \
  --domain local-inspection \
  --owned "task packet compiler" \
  --owned "local Git evidence" \
  --forbidden "network access" \
  --forbidden "cross-repository mutation" \
  --json > task-packet.json
```

Record a reported successful result. The command intentionally exits nonzero because the references have not been independently verified:

```bash
continuum result task-packet.json \
  --outcome succeeded \
  --evidence git_status=passed=artifacts/git-status.txt \
  --evidence changed_files=passed=artifacts/diff-stat.txt \
  --evidence validation_results=passed=artifacts/validation.json \
  --evidence commit_sha=passed=abc123 \
  --domain-availability unverified \
  --json
```

A blocked or failed outcome requires a structured blocker and permits a `ready -> blocked` decision without pretending that completion evidence passed:

```bash
continuum result task-packet.json \
  --outcome blocked \
  --blocker-code human.intent_required \
  --blocker-message "A product-policy decision is required." \
  --json
```

Run the repository checks:

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
```

## Repository contract

A governed repository embeds `.continuum/repository.json` with repository identity, named commands, protected paths, forbidden operations, and required evidence.

The central engine owns protocol and decision machinery. Each governed repository owns its local intent, commands, boundaries, and proof requirements.

## Execution domains

A repository separately declares where work could eventually run:

```json
{
  "schema_version": 1,
  "default_domain": "local-inspection",
  "domains": {
    "local-inspection": {
      "transport": "local",
      "lifecycle": "external",
      "auto_start": false,
      "capabilities": ["inspect"]
    }
  }
}
```

Execution domains prevent the orchestrator, an agent, or a CLI command from treating an arbitrary shell as an implicit control surface. A declaration only describes policy and capability. It does not prove that a domain is attached, reachable, authenticated, or healthy.

Result packets currently preserve domain availability as `unverified`. `observed` and `unavailable` states are rejected until a capability-checked adapter can independently verify and normalize the evidence.

The domain model is informed by [WezTerm](https://github.com/wezterm/wezterm), whose multiplexer separates named local and remote domains, lifecycle, transport, and spawn behavior from its CLI. Continuum adopts that architectural boundary without vendoring WezTerm or claiming a terminal adapter. See [`docs/prior-art/wezterm.md`](docs/prior-art/wezterm.md).

## Result and transition contracts

A result packet contains:

- a deterministic result ID and originating task ID;
- repository and task HEAD identity;
- caller-reported evidence records in `NAME=STATUS=REFERENCE` form;
- a completion gate listing reported passes, failures, skips, missing evidence, and verification blockers;
- an unverified domain observation;
- a transition decision from `ready` to `completed` or `blocked`;
- `applied: false`, because state persistence is outside the current proof boundary.

A `succeeded` outcome does not permit completion from caller-reported statuses alone. Missing, failed, or skipped evidence produces a blocked gate; otherwise the gate remains `unverified` until a future independent verifier produces authoritative proof. Blocked and failed outcomes require a structured blocker and may permit the blocked terminal decision.

## Project structure

```text
.continuum/                 Repository and execution-domain contracts
.github/workflows/          Automated validation
schemas/                    Repository, domain, task, and result schemas
docs/                       Architecture, decisions, and prior-art analysis
scripts/                    Dependency-free repository validation
src/continuum/              Contracts, gates, workflow decisions, packets, and CLI
tests/                      Executable contract and decision behavior
AGENTS.md                    Agent operating contract
```

## Next vertical slices

1. Add verified artifact readers so completion gates can distinguish reported evidence from independently validated evidence.
2. Add branch-topology governance so unnecessary stacked PRs are rejected by policy.
3. Persist workflow state and apply only previously permitted transitions.
4. Execute allow-listed repository commands only through a capability-checked domain adapter.
5. Add provider-neutral agent adapters behind the same task/result contracts.
6. Evaluate a WezTerm CLI/multiplexer adapter after execution and evidence contracts are proven.
7. Prove a complete loop in The Blacksmith Guild before enabling broader automation behavior.

See [`docs/architecture.md`](docs/architecture.md) for actor boundaries, execution domains, packet contracts, state ownership, and the current implementation boundary.

## License

Continuum is available under the [MIT License](LICENSE).
