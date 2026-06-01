Status: ACCEPTED

Date: 2026-05-28

# ADR-011: Three-Tier Benchmark Locking

## Context

Benchmark consistency has been undermined by ad hoc edits to workspaces, oracle impls, and audited tests after scores were produced — making runs non-comparable with no explicit lifecycle state governing what may change. ADR-010 already froze the canonical engine and `test_utils` for Phase 18 to preserve comparability; this ADR generalizes that one-off freeze into an explicit, machine-enforced lifecycle for every benchmark.

## Decision

Each benchmark declares a **tier** in its config (`benchmarks/sos/config.json`). Three tiers with monotonically increasing lock scope:

- **Beta** — everything editable: `workspace/`, oracle impls and oracle `engine/`, audited tests.
- **Benchmarking** — `workspace/` is LOCKED; oracle impls/engine and audited tests remain editable.
- **Released** — all three are LOCKED: workspace, oracle impls/engine, and audited tests.
Locking oracle impls at Released — beyond the original "workspace + audited tests" note — is required so audited tests cannot be silently invalidated after release.

Tier transitions are **forward-only and non-reversible except for grave, explicitly documented reasons**:

- **Benchmarking → Beta** invalidates all existing benchmarks for that identity.
- **Released → Benchmarking** forces retraction of all published scores.
Enforcement is a **CI check** that reads the **base branch's** `tier`, expands it to locked path-globs, runs `git diff --name-only base...head`, and fails the PR if any changed path matches a locked glob. Locked paths by tier: Benchmarking locks `benchmarks/<bench>/workspace/`; Released additionally locks the oracle impls/engine (`benchmarks/<bench>/data/test_oracle_workspace/`) and audited tests (`benchmarks/<bench>/data/tests/audited/`). `config.json` is **never** a locked path, so a pure tier-transition PR (touching only `config.json`) always passes — and because a PR's edits are judged against the base (pre-transition, stricter) tier, lowering a tier and editing newly-unlocked files in the *same* PR is structurally impossible; those edits must land in a follow-up PR after the transition merges. No bypass label or transition carve-out is required. The tier is flipped via a human PR edit to `config.json`. SOS is currently in **Benchmarking**.

## Tier Transition Log

Tier transitions are recorded here — there is no separate log file. Each entry notes the date, benchmark identity, direction, and triggering reason; for any →Released transition it also records the result of the required pre-Release harvest + investigation pass (see [AUDITED-TEST-IMPROVEMENT-WORKFLOW.md](https://www.notion.so/b99a10aff98e4794856ce259e4916163) → Cadence). Downgrades additionally note the invalidation (Benchmarking→Beta) or score retraction (Released→Benchmarking) they trigger.

- 2026-05-28 — `sos` set to **Benchmarking** (initial tiering; `workspace/` locked).
## Consequences

- **Positive**: Scores are comparable within a tier. "What may change" is explicit and machine-enforced. Because Released freezes audited tests, the manual investigation/discovery skill (v1 Test Harvester) and any test promotion run only *before* Release — so Released scores never drift.
- **Negative**: Revising a Released benchmark is heavyweight — either a documented retraction of published scores, or a new versioned benchmark identity. Some friction for legitimate late fixes.
- **Neutral**: Tier state lives in `config.json` and is human-controlled; there is no automated promotion between tiers.
## Alternatives Considered

- **Immutable Released, revise only by forking to a new versioned identity** (e.g. `benchmarks/sos-v2/`): cleanest provenance, but heavier for every correction. Rejected in favor of allowing in-place reversal with explicit invalidation/retraction.
- **No formal tiers, rely on reviewer discipline**: the status quo that produced the inconsistency. Rejected.
- **Lock audited tests at Benchmarking too**: rejected — the point of Benchmarking is to keep refining oracle impls and audited tests while the workspace agents see stays fixed.
