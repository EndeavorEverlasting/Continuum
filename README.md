# Continuum

**A local orchestration engine that carries repository context, evidence, and workflow state across agents, sessions, and development sprints.**

Continuum is intended to remove the human from repetitive software-development coordination without removing the human from intent. A repository carries its own operating contract. Deterministic tooling performs inspection and validation. Replaceable agents receive bounded work only when reasoning is actually required.

## The model

Continuum treats software development as a controlled loop among five actors:

- **Human:** intent, priorities, policy, and exceptions.
- **Repository:** durable memory, contracts, code, tests, and decisions.
- **Orchestrator:** state observation, task selection, execution, validation, and transition.
- **Agent:** bounded reasoning and implementation.
- **Environment:** Git, CI, runtime, artifact, and service signals.

```text
observe -> classify -> compile task -> execute -> validate -> record -> transition
```

The repository and its evidence carry continuity. A chat session or model does not.

## Current proof boundary

Continuum `0.2.0` provides two executable foundations:

- dependency-free validation of an embedded `.continuum/repository.json` contract;
- bounded task-packet compilation from that contract and read-only local Git evidence.

The task packet captures:

- repository identity and declared commands;
- protected paths, forbidden operations, and required evidence;
- explicit owned and forbidden sprint scope;
- Git root, branch, HEAD SHA, dirty state, short status, and recent commits;
- a deterministic task ID suitable for handoff to any agent provider.

Continuum does **not** yet execute commands, dispatch agents, record result packets, advance workflow states, mutate GitHub, or operate across repositories.

## Quick start

Continuum requires Python 3.11 or newer.

```bash
git clone https://github.com/EndeavorEverlasting/Continuum.git
cd Continuum
python -m pip install --no-deps -e .
continuum doctor .
continuum doctor . --json
```

Compile a bounded task packet:

```bash
continuum task . \
  --owned "task packet compiler" \
  --owned "local Git evidence" \
  --forbidden "network access" \
  --forbidden "cross-repository mutation" \
  --json
```

Both `--owned` and `--forbidden` are required and repeatable. Continum blocks rather than inventing missing scope.

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

## Project structure

```text
.continuum/                 Continuum's own embedded repository contract
.github/workflows/          Automated validation
schemas/                    Repository and task-packet schemas
docs/                       Architecture and operating doctrine
scripts/                    Dependency-free repository validation
src/continuum/              Contract, Git-evidence, task-packet, and CLI code
tests/                      Executable contract and task-packet behavior
AGENTS.md                    Agent operating contract
```

## Next vertical slices

1. Add result packets and deterministic completion gates.
2. Model explicit workflow states and permitted transitions.
3. Execute only allow-listed repository commands from a task packet.
4. Add provider-neutral agent adapters behind the same task/result contracts.
5. Prove a complete loop in The Blacksmith Guild before enabling broader automation behavior.

See [`docs/architecture.md`](docs/architecture.md) for actor boundaries, task-packet contents, state ownership, and the current implementation boundary.

## License

Continuum is available under the [MIT License](LICENSE).
