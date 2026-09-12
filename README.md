# Continuum

> **Status: DORMANT / PRESERVED REFERENCE**  
> **Active control plane:** [`EndeavorEverlasting/AgentSwitchboard`](https://github.com/EndeavorEverlasting/AgentSwitchboard)

Continuum is no longer an active orchestration product or roadmap target. Its existing `0.4.0` implementation is preserved for reference, validation, and historical design context.

The authoritative lifecycle decision is:

- `.continuum/lifecycle.json`
- `docs/adr/0001-continuum-dormant.md`

While dormant, feature development and runtime/orchestration expansion are not allowed. The only permitted changes are security fixes, dependency fixes, archival maintenance, and documentation corrections.

There is **no automatic reactivation gate**. Any future attempt to make Continuum active again requires a new explicit architecture decision by the repository owner that first changes the machine-readable lifecycle contract.

## Why it is dormant

AgentSwitchboard now owns the active control-plane responsibilities Continuum was originally expected to grow into, including agent/model routing, bootstrap/runtime resolution, child-agent coordination, repository execution flows, intervention, validation, and evidence-driven completion. Maintaining two active orchestration systems would duplicate ownership and add avoidable complexity.

## Preserved implementation

Continuum `0.4.0` contains reference implementations for:

- repository-contract inspection;
- named execution-domain validation;
- read-only Git evidence and provider-neutral task packets;
- result packets that cannot authorize completion without independent verification;
- deterministic branch-topology decisions.

These surfaces remain useful historical/reference material. They are not active control-plane dependencies.

## Historical control loop

The preserved implementation modeled:

```text
observe -> classify -> topology gate -> compile task + domain -> execute -> record result -> evidence gate -> transition
```

That model is retained for reference only. Active orchestration belongs to AgentSwitchboard.

## Validation

Dormant repositories still need to remain internally coherent:

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python -m compileall -q src tests scripts
python -m pip install --no-deps -e .
```

Passing these checks proves repository consistency only. It does not reactivate Continuum.

## Structure

```text
.continuum/                 Repository contracts, including lifecycle status
schemas/                    Machine-readable preserved contracts
docs/adr/                   Architecture decisions
src/continuum/              Preserved deterministic implementation
tests/                      Contract and regression tests
AGENTS.md                    Dormant repository operating contract
```

Continuum is available under the [MIT License](LICENSE).
