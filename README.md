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
- immutable result-packet compilation with structural completion gates, caller-reported domain observations, and explicit workflow-transition decisions.

A task packet captures repository identity, scope, Git state, proof requirements, and a named execution domain. A result packet binds reported evidence and outcome back to that task ID, evaluates whether required evidence structurally passed, and decides whether `ready -> completed` or `ready -> blocked` is permitted.

Continuum does **not** yet execute commands, verify referenced artifact contents, attach to terminals, apply workflow state, dispatch agents, mutate GitHub, or operate across repositories. Result evidence and domain observations are explicitly labeled `caller-reported`, and every transition is emitted with `applied: false`.

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

Compile a successful result packet only when every required evidence record has a status and durable reference:

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

A result packet may record domain availability as `unverified`, `observed`, or `unavailable`. `observed` and `unavailable` require an evidence reference. Observed capabilities must be a subset of the capabilities declared by the task. Continuum records those statements as caller-reported evidence; it does not manufacture runtime proof.

The domain model is informed by [WezTerm](https://github.com/wezterm/wezterm), whose multiplexer separates named local and remote domains, lifecycle, transport, and spawn behavior from its CLI. Continuum adopts that architectural boundary without vendoring WezTerm or claiming a terminal adapter. See [`docs/prior-art/wezterm.md`](docs/prior-art/wezterm.md).

## Result and transition contracts

A result packet contains:

- a deterministic result ID and originating task ID;
- repository and task HEAD identity;
- caller-reported evidence records in `NAME=STATUS=REFERENCE` form;
- a completion gate listing passed, failed, skipped, and missing evidence;
- a caller-reported domain observation with optional observed capabilities;
- a transition decision from `ready` to `completed` or `blocked`;
- `applied: false`, because state persistence is outside the current proof boundary.

A succeeded outcome permits completion only when every task-required evidence record is present and passed. Blocked and failed outcomes require a structured blocker and permit the blocked terminal decision without evaluating completion evidence as successful.

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

1. Add verified artifact readers so completion gates can distinguish reported evidence from artifact-validated evidence.
2. Persist workflow state and apply only previously permitted transitions.
3. Execute allow-listed repository commands only through a capability-checked domain adapter.
4. Add provider-neutral agent adapters behind the same task/result contracts.
5. Evaluate a WezTerm CLI/multiplexer adapter after execution and evidence contracts are proven.
6. Prove a complete loop in The Blacksmith Guild before enabling broader automation behavior.

See [`docs/architecture.md`](docs/architecture.md) for actor boundaries, execution domains, packet contracts, state ownership, and the current implementation boundary.

## License

Continuum is available under the [MIT License](LICENSE).
