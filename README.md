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
observe -> classify -> compile task + domain -> execute -> validate -> record -> transition
```

The repository and its evidence carry continuity. A chat session or model does not.

## Current proof boundary

Continuum `0.2.0` provides three executable foundations:

- dependency-free validation of an embedded `.continuum/repository.json` contract;
- validation and resolution of named execution domains from `.continuum/execution-domains.json`;
- bounded task-packet compilation from those contracts and read-only local Git evidence.

The task packet captures:

- repository identity and declared commands;
- protected paths, forbidden operations, and required evidence;
- explicit owned and forbidden sprint scope;
- Git root, branch, HEAD SHA, dirty state, short status, and recent commits;
- a named execution domain with transport, lifecycle, auto-start policy, and capabilities;
- explicit `unverified` domain availability so configuration is never mistaken for runtime proof;
- a deterministic task ID suitable for handoff to any agent provider.

Continuum does **not** yet execute commands, attach to terminals, dispatch agents, record result packets, advance workflow states, mutate GitHub, or operate across repositories.

## Quick start

Continuum requires Python 3.11 or newer.

```bash
git clone https://github.com/EndeavorEverlasting/Continuum.git
cd Continuum
python -m pip install --no-deps -e .
continuum doctor .
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
  --json
```

`--owned` and `--forbidden` are required and repeatable. `--domain` is optional and resolves to the registry default when omitted. Continuum blocks rather than inventing missing scope or an undeclared execution target.

Run the repository checks:

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
```

## Repository contract

A governed repository embeds `.continuum/repository.json`:

```json
{
  "schema_version": 1,
  "harness_version": "0.2.0",
  "repository": {
    "name": "Example",
    "default_branch": "main"
  },
  "commands": {
    "test": "python -m unittest"
  },
  "boundaries": {
    "protected_paths": ["LICENSE"],
    "forbidden_operations": ["force_push"]
  },
  "evidence": {
    "required": ["validation_results", "commit_sha"]
  }
}
```

The central engine owns protocol and execution machinery. Each governed repository owns its local intent, commands, boundaries, and proof requirements.

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

Execution domains prevent the orchestrator, an agent, or a CLI command from treating an arbitrary shell as an implicit control surface. A declaration only describes policy and capability. It does not prove that a domain is attached, reachable, authenticated, or healthy. Runtime availability must later arrive as environment evidence and be recorded in a result packet.

The domain model is informed by [WezTerm](https://github.com/wezterm/wezterm), whose multiplexer separates named local and remote domains, lifecycle, transport, and spawn behavior from its CLI. Continuum adopts that architectural boundary without vendoring WezTerm or claiming a terminal adapter. See [`docs/prior-art/wezterm.md`](docs/prior-art/wezterm.md).

## Project structure

```text
.continuum/                 Repository and execution-domain contracts
.github/workflows/          Automated validation
schemas/                    Repository, execution-domain, and task-packet schemas
docs/                       Architecture, decisions, and prior-art analysis
scripts/                    Dependency-free repository validation
src/continuum/              Contract, domain, Git-evidence, task-packet, and CLI code
tests/                      Executable contract, domain, and task-packet behavior
AGENTS.md                    Agent operating contract
```

## Next vertical slices

1. Add result packets, runtime-domain observations, and deterministic completion gates.
2. Model explicit workflow states and permitted transitions.
3. Execute allow-listed repository commands only through a capability-checked domain adapter.
4. Add provider-neutral agent adapters behind the same task/result contracts.
5. Evaluate a WezTerm CLI/multiplexer adapter after execution and evidence contracts are proven.
6. Prove a complete loop in The Blacksmith Guild before enabling broader automation behavior.

See [`docs/architecture.md`](docs/architecture.md) for actor boundaries, execution domains, task-packet contents, state ownership, and the current implementation boundary.

## License

Continuum is available under the [MIT License](LICENSE).
