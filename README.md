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
observe -> classify -> select -> execute -> validate -> record -> transition
```

The repository and its evidence carry continuity. A chat session or model does not.

## Current proof boundary

Continuum `0.1.0` provides one small, executable foundation:

- an embedded `.continuum/repository.json` contract;
- a formal JSON Schema for that contract;
- a dependency-free `doctor` command;
- syntactic-English and JSON evidence output;
- explicit nonzero failure behavior for missing or invalid contracts;
- unit tests and CI validation.

It does **not** yet dispatch agents, mutate other repositories, schedule workflows, or claim autonomous software development.

## Quick start

Continuum requires Python 3.11 or newer.

```bash
git clone https://github.com/EndeavorEverlasting/Continuum.git
cd Continuum
python -m pip install --no-deps -e .
continuum doctor .
continuum doctor . --json
```

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
  "harness_version": "0.1.0",
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
schemas/                    Versioned contract schemas
docs/                       Architecture and operating doctrine
scripts/                    Dependency-free repository validation
src/continuum/              CLI and contract inspection
tests/                      Executable contract and CLI behavior
AGENTS.md                    Agent operating contract
```

## Next vertical slices

1. Compile a bounded task packet from repository and Git evidence.
2. Model explicit workflow states and permitted transitions.
3. Record result packets and deterministic completion gates.
4. Add provider-neutral agent adapters behind the same task contract.
5. Prove a complete loop in The Blacksmith Guild before extracting broader automation behavior.

See [`docs/architecture.md`](docs/architecture.md) for actor boundaries, state ownership, and the current implementation boundary.

## License

Continuum is available under the [MIT License](LICENSE).
