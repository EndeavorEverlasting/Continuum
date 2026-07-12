# WezTerm prior-art analysis

Continuum uses [WezTerm](https://github.com/wezterm/wezterm) as architectural prior art for separating orchestration intent from terminal and process topology. This document records the concepts adopted by Continuum so future implementation does not collapse back into ad hoc shell invocation.

The review was performed against WezTerm commit `fff02ca501c3b457f99b467a86061d2b150c51f2`.

## Relevant WezTerm contracts

- [`docs/multiplexing.md`](https://github.com/wezterm/wezterm/blob/fff02ca501c3b457f99b467a86061d2b150c51f2/docs/multiplexing.md) defines multiplexing around named domains and documents local, Unix, SSH, TLS, and WSL connection models.
- [`mux/src/domain.rs`](https://github.com/wezterm/wezterm/blob/fff02ca501c3b457f99b467a86061d2b150c51f2/mux/src/domain.rs) gives domains explicit spawn, attach, detach, state, identity, and capability behavior.
- [`wezterm/src/cli/mod.rs`](https://github.com/wezterm/wezterm/blob/fff02ca501c3b457f99b467a86061d2b150c51f2/wezterm/src/cli/mod.rs) keeps the CLI as a client of a GUI or background mux server, makes auto-start policy explicit, and supports machine-readable output.

## Patterns Continuum adopts

| WezTerm pattern | Continuum application |
| --- | --- |
| Named multiplexer domains | Named repository-local execution domains selected by task packets. |
| Transport-specific domain implementations | A transport field and future adapter boundary for local, Unix, SSH, TLS, WSL, serial, or custom targets. |
| Explicit attach, detach, spawnability, and state | Declared capabilities now; observed availability and lifecycle transitions later in result/environment evidence. |
| Explicit server auto-start policy | `auto_start` is a contract field and is never inferred. External-lifecycle domains cannot auto-start. |
| CLI as client rather than state owner | Continuum CLI compiles and displays contracts; durable state belongs to repositories and future runtime stores. |
| Structured CLI output | Task packets and blockers remain machine-readable JSON independently from human-readable output. |
| Stable local/remote identity mapping | Future adapters must reconcile external identifiers into durable Continuum IDs rather than leaking provider identity into workflow contracts. |

## Patterns Continuum does not adopt

- WezTerm's window, tab, pane, rendering, keyboard, or GUI object model.
- WezTerm's RPC protocol, daemon implementation, socket paths, authentication, or remote bootstrap behavior.
- Automatic process spawning or connection attempts during task compilation.
- An assumption that WezTerm is installed or is the only terminal provider.

No WezTerm source code is vendored or copied. The relationship is architectural and documentary.

## Current proof boundary

Continuum validates `.continuum/execution-domains.json`, resolves a named domain, and embeds that declaration in a deterministic task packet. Domain availability is always emitted as `unverified` because no runtime probe occurs.

The next safe progression is:

1. define result-packet and runtime-observation schemas;
2. define domain state transitions and completion gates;
3. implement an allow-listed local adapter behind the domain contract;
4. prove process lifecycle and evidence capture without an AI agent;
5. then evaluate a WezTerm CLI/mux adapter as one replaceable provider.

A future WezTerm adapter must use structured identifiers and output where available, treat terminal content as untrusted data, and never convert pane text into orchestration instructions.
