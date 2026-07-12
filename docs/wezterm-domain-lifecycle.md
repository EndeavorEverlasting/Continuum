# WezTerm-derived execution-domain lifecycle

Continuum now incorporates a concrete subset of WezTerm's multiplexer-domain
model rather than borrowing only its transport names.

## Authoritative source

The adoption is pinned in
`.continuum/wezterm-contributions.json` to WezTerm commit
`fff02ca501c3b457f99b467a86061d2b150c51f2`.

Authority paths:

- `mux/src/domain.rs`
- `lua-api-crates/mux/src/domain.rs`
- `wezterm-client/src/domain.rs`
- `docs/multiplexing.md`

WezTerm models a domain as a distinct multiplexer with a stable identity,
declared spawn/detach behavior, explicit attach and detach operations, and an
attached or detached state. Its client layer separately reconciles remote
resource identifiers with local handles. Its multiplexing guide also
distinguishes connecting the client at startup from starting or serving the
domain itself.

## Adopted now

Continuum adds a provider-neutral domain snapshot and decision engine:

```text
declared execution-domain capabilities
+ independently verified attached/detached state
+ requested attach/detach/spawn action
= allowed or blocked non-mutating decision
```

The decision always reports `"applied": false`. No transport, shell, process,
terminal, multiplexer, or remote host is touched.

Key rules:

1. A configured capability is not proof that a domain is currently available.
2. Caller-reported state cannot authorize state-sensitive actions.
3. Spawn requires an independently verified attached domain.
4. `auto_start` controls a future managed service lifecycle; it does not imply
   that a client is attached.
5. Repeated attach or detach requests are explicit idempotent decisions.
6. Remote and local resource identifiers must not be treated as interchangeable.

## Command

```bash
python scripts/evaluate-domain-action.py domain-snapshot.json \
  --repository . \
  --action attach \
  --json
```

Example snapshot:

```json
{
  "$schema": "schemas/execution-domain-snapshot.schema.json",
  "schema_version": 1,
  "kind": "continuum.execution-domain-snapshot",
  "domain": "local-inspection",
  "state": "unverified",
  "verification": "unverified",
  "evidence_reference": null
}
```

The current `local-inspection` domain deliberately lacks attach, detach, and
spawn capabilities, so those requests remain blocked.

## Deferred

Continuum does not yet adopt:

- WezTerm's PTY or process-spawn implementation;
- Unix, SSH, TLS, WSL, serial, or tmux transports;
- automatic client connection;
- remote/local pane, tab, or window ID synchronization;
- terminal GUI, input, clipboard, scrollback, or rendering behavior;
- a live provider adapter that observes domain state or applies decisions.

The remote/local identity reconciliation pattern remains registered as
`reference_only` until Continuum has a real multi-client workspace resource
model.

## Proof level

This sprint reaches:

- source-pinned architecture proof;
- contract proof;
- harness decision proof;
- static-test proof.

It does not reach attach, detach, spawn, terminal, multiplexer, or live-runtime
proof.
