# Branch-topology governance

Continuum treats branch selection as a deterministic policy decision, not an agent preference.

Before branch creation, the environment supplies a normalized snapshot containing the canonical branch SHA, proposed base SHA and cleanliness, open PR states, check states, and any requested stacking exception. Continuum reads the repository's committed `branch_policy` and emits an immutable decision.

The gate blocks:

- dirty bases when clean bases are required;
- stale canonical branches;
- a feature base whose green, mergeable PR should be merged first;
- stacked work when policy forbids it;
- noncanonical bases without a reasoned exception under `explicit_only` policy.

The gate permits a clean, current canonical base and only deliberately authorized stacking.

The `topology` command is read-only. It neither fetches GitHub nor creates, merges, retargets, or deletes branches and pull requests. Environment adapters remain responsible for producing truthful snapshots and separately applying an allowed decision.
