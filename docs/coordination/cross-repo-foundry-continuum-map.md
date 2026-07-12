# Cross-repository control-plane and expert-reference sprint map

**Snapshot:** 2026-07-12

**Coordination home:** `EndeavorEverlasting/Continuum`

**Lane:** coordinator / cleanup / cross-repository architecture

**Proof boundary:** remote repository and pull-request evidence only; local dirty state, conflicts, in-progress Git operations, ignored artifacts, and worktrees remain unverified.

## Purpose

Foundry, Continuum, and BlacksmithGuild share a contract-first, evidence-first spirit, but they should not become duplicate products.

The intended authority chain is:

```text
Foundry discovers and explains recoverable repository value.
Continuum decides how bounded work may be replayed and proven.
The application repository adapts the value, proves parity, and retains domain authority.
```

This map also classifies external tools as things to clone, use, integrate, emulate, evaluate, defer, or retain only as references. The machine-readable catalog is `.continuum/expert-references.json`.

## Product boundary

| System | Primary responsibility | Should contain | Should not absorb |
|---|---|---|---|
| **Foundry** | Repository intelligence and engineering observability | Git and provider ingestion, normalized branch/commit/PR facts, drift, staleness, conflict risk, capability inference, readiness analysis, storage, jobs, dashboards, portfolio views | Agent task authority, application runtime authority, or proof claims that exceed collected evidence |
| **Continuum** | Development-state orchestration and evidence control | Bounded task/result packets, topology gates, provenance, execution-domain contracts, selective replay plans, validation and completion gates, handoffs | Portfolio dashboards, a second copy of Foundry analysis/storage, terminal runtime code, or application policy |
| **BlacksmithGuild** | Application-owned proof laboratory | Bannerlord/runtime adapters, game policy, app validators, proof taxonomy, reusable capability exports, standalone fallbacks | Generic cross-repository coordination once the capability has proven portability and extraction gates |
| **Other application repos** | Product and runtime authority | Their own adapters, tests, policy, evidence, and operator contracts | Reliance on Continuum or Foundry for build or runtime survival |

### Why Foundry and Continuum overlap

Both reason about branches, pull requests, evidence, readiness, and policy. The distinction is the output:

- Foundry answers **what exists, what changed, what is stale, what may be valuable, and what deserves attention**.
- Continuum answers **what bounded operation is permitted next, from which exact source, under which proof and topology gates, and how the result is closed out**.

Foundry's current Git and analysis packages are useful inputs. Its policy package is still a permissive seam, so Continuum must retain orchestration authority until a real independently tested policy integration exists.

## Selective replay and cherry-pick boundary

The future recovery loop must preserve utility from commits, paths, hunks, and review comments without blindly merging stale heads.

```text
Foundry collector and analysis
  -> exact recovery candidates
  -> Continuum replay classification and task packet
  -> isolated current-base worktree
  -> selective commit/path/hunk reconstruction
  -> application-owned validators and parity proof
  -> replacement PR with provenance
  -> explicit source PR/comment/branch disposition
```

### Foundry-owned candidate packet

Foundry should eventually emit a read-only packet containing:

- source repository and provider;
- pull request, branch, and exact head SHA;
- exact commit, path, hunk, or review-comment identifiers;
- ahead, behind, divergence, conflict-risk, and staleness facts;
- capability classification and confidence;
- whether equivalent value appears present on the current canonical branch;
- proposed disposition: `keep`, `superseded`, `reject`, `needs_owner_review`, or `needs_runtime_proof`;
- no mutation command and no completion claim.

### Continuum-owned replay packet

Continuum should:

- verify the canonical base and local floor;
- require a dedicated branch or worktree lease;
- preserve source provenance;
- choose whole-commit cherry-pick only when the commit remains coherent;
- otherwise select a path, reviewed hunk, or current-source reconstruction;
- carry review comments as acceptance requirements, not patches;
- require current validators and proof-level classification;
- refuse source closure until every useful item has a replacement, rejection, retention, or explicit blocker;
- emit `applied: false` until an authorized adapter performs the Git operation and independently records the result.

### Application-owned closeout

The application repository must:

- adapt generic value to current source and policy;
- preserve standalone build, validation, and runtime fallback;
- prove parity before deleting or delegating app-owned harness code;
- distinguish historical evidence from fresh proof;
- authorize closure or archival of the source PR and branch.

## Remote repository floor

| Repository | Inspected authority | Open PR map | Remote disposition | Safe next base |
|---|---|---|---|---|
| `EndeavorEverlasting/Continuum` | `main@0952ae73a97e6b08a63668b02f3ddb0b79a86ed0` | #5 is the active WezTerm domain-lifecycle lane; #3 is a separate completion-proof lane | Do not stack new coordination work on either PR | Current `main`, after local clean-floor verification |
| `EndeavorEverlasting/BlacksmithGuild` | `main@75078deba98dd8d7133e175c9195e8aa94012c4c` | #43 is active; older open inventory includes #38, #35, #34, #33, #32, #31, #30, #29, #28, #24, #20, #9, #8, #6, #5, and #2 | Use merged #58/#59 recovery plans; do not treat #43 as stale input | Current `main`, one bounded replacement lane per recovery unit |
| `EndeavorEverlasting/foundry` | default branch `feature/2026-04-25-foundry-release-control-plane@a1f506f3e6fe5d66ca83c722a6484cb735936fd0` | #1 branch naming, #2 extraction forensics, #3 mainline promotion insights | Canonical-base governance is unresolved; the dated feature default is an operational risk | **Blocked:** choose and prove a canonical branch before new product lanes |

## Worktree map

The connector environment cannot inspect local clones, dirty files, conflicts, ignored/generated artifacts, or attached worktrees. No local checkout is declared safe by this document.

Run these commands in each local repository before changing it:

```bash
git fetch origin --prune
git status --short
git branch --show-current
git log --oneline --decorate -8
git worktree list --porcelain
git diff --name-only --diff-filter=U
gh pr list --state open --limit 50
```

Stop and preserve local work when any repository is:

- dirty or conflicted;
- mid-merge, rebase, cherry-pick, revert, or bisect;
- on a branch owned by another sprint;
- ahead or diverged without classified local commits;
- carrying unclassified generated or ignored evidence.

Use one sibling worktree per replay or tool experiment. Never use a stale PR head as a generic base.

## Pull-request map and launch order

### Wave 0 — prove each local floor

1. Run the exact local commands above.
2. Record primary paths, branch, HEAD, upstream, dirty/conflicted state, worktrees, and in-progress Git operations.
3. Classify generated and ignored artifacts.
4. Do not delete branches or worktrees.

### Wave A — settle canonical bases

- **Continuum:** keep #3 and #5 separate; merge or update them only through their own proof gates.
- **BlacksmithGuild:** keep #43 in its active runtime/harness lane; use the merged recovery manifest for older PRs.
- **Foundry:** decide whether the dated release-control-plane branch becomes a renamed canonical base or whether a new `main` is created from a proven commit. Retarget #1–#3 only after that decision.

### Wave B — define the cross-repository recovery packet

A Foundry sprint should define the read-only candidate packet. A separate Continuum sprint should define its importer and replay-plan schema. Neither sprint should execute Git mutations.

Collision boundary:

```text
Foundry: collector, normalizer, analysis, packet producer
Continuum: packet consumer, topology, task/replay decision, proof gate
Application repo: adapter, validators, parity, source disposition
```

### Wave C — prove one low-risk replay

Use a docs/schema-only source item whose current-source equivalent is easy to test.

The replacement PR must name:

- source PR, branch, head, commit, path/hunk/comment;
- selected value;
- rejected or superseded value;
- current canonical base;
- validation;
- proof reached and not reached;
- old PR and branch disposition.

Do not begin with runtime code or BlacksmithGuild PR #43.

### Wave D — isolated external-tool experiments

Run each tool as a separate lane:

- `skills` CLI: one project-local read-only skill.
- `treehouse`: compare worktree pooling with Continuum leases and floor checks.
- `no-mistakes`: docs-only delivery-gate comparison.
- `firstmate`: isolated read-only scout using a Continuum packet.
- `lavish-axi`: local visual review with annotations preserved as untrusted review input.
- AXI: interface audit without behavior change.
- `gnhf`: non-mutating fixture only.
- OpenSuperWhisper: deferred; preserve a provider-neutral voice-input boundary.

## Expert-reference disposition language

| Disposition | Meaning |
|---|---|
| `clone` | Obtain a separate local copy for evaluation; never vendor it into Continuum by implication |
| `use` | Operate the tool as an external dependency or operator aid |
| `integrate` | Build a bounded adapter or packet boundary |
| `emulate` | Adopt a design principle while writing Continuum-owned implementation |
| `reference_only` | Preserve as expert prior art; no dependency or adapter yet |
| `evaluate` | Run an isolated, reversible experiment before adoption |
| `defer` | Record the tool but block active adoption until prerequisites exist |

## Safety and collision rules

- Never let an external coordinator override repository contracts.
- Never infer runtime proof from panes, sessions, review UIs, dictation, or agent status.
- Never install or clone multiple tool experiments into the same sprint worktree.
- Never close a stale PR because its branch is old.
- Never squash away unique comments, acceptance requirements, or provenance before disposition.
- Never move application-domain policy into Continuum merely because it is reusable-looking.
- Never recreate Foundry's portfolio intelligence and persistence inside Continuum.
- Never let Foundry's current no-op policy seam authorize a mutation.

## Changed-file boundary for this sprint

This coordination sprint owns only:

```text
.continuum/expert-references.json
schemas/expert-reference-catalog.schema.json
docs/coordination/cross-repo-foundry-continuum-map.md
```

It does not modify product code, CI, runtime adapters, existing task/result/topology contracts, or application repositories.

## Exact next command

Run in the local Foundry checkout first because its canonical base is unresolved:

```bash
git fetch origin --prune && git status --short && git branch --show-current && git log --oneline --decorate -8 && git worktree list --porcelain && gh pr list --state open --limit 20
```
