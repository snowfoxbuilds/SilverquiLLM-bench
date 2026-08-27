Status: RETIRED (grilling 2026-08-27) — the checkpoint/capability-DAG design solved bounded-context sequential implementation over a ~281-card pool. The HOB benchmarks that succeed MSH are 5–20-card problem sets consumed in a single run, so the problem no longer exists; ADR-008/009 resume legs cover crash recovery. Nothing here is load-bearing for HOB.

Last updated: 2026-06-10

# MSH Checkpoints

The MSH benchmark is an ordered sequence of card-group steps, each ending in a frozen, reference-validated snapshot — the unit of resume, regression attribution, and bounded agent context.

## Context

The additive-engine rule (ADR-010) needs an operational counterpart: a known-good baseline you can resume from, attribute regressions to, and bound per-step context with. The benchmark becomes an ordered partition S1 → S2 → ... → Sk of the card pool.

## Design

### What a checkpoint is

A checkpoint Ci is a frozen, reference-validated snapshot of the whole workspace taken after card group Si:

- the engine at that point (canonical + all additive diffs so far)
- the `card_impl.py` files for every card in S1..Si
- the audited tests in scope
- the green ledger (which cards/tests passed) plus the RNG seeds and engine version that produced it
A checkpoint is blessed only when the accumulated suite is at a recorded state under the reference harness.

### Goal 1 — valid resuming

- Resume is a clean reload, not a replay: pinned determinism (RNG seed, engine version, fixture state, deferred-ordering decisions).
- The checkpoint bundles its own engine diff for reproducibility (the eval-side patch application is fixed on main, but checkpoints still carry their diff).
- Blast-radius cap: a step that times out or crashes forfeits only that step; resume from the previous checkpoint.
### Goal 2 — fair engine-regression metric

- At each checkpoint run the full accumulated suite (S1..Si), not just Si's tests.
- Engine Regression = a card green at the previous checkpoint that goes red at this one, attributed to the current step. Enables a per-step breakage rate (regressions / prior-green).
- Only fair if later steps are genuinely additive: a step that must change engine behavior needs an explicit re-baseline event that re-blesses the green ledger.
### Goal 3 — leveling context across agents

- Each step hands the agent a standardized, bounded context package: the frozen engine + its API doc, the accumulated decisions/ADR log, and the current group's oracle texts + audited tests — not the full transcript of prior cards.
- Summary state substitutes for raw history, so small- and large-context models face comparable per-step loads.
### Standardized randomness

All random effects (coin flips, shuffles, random selection) draw from a single seeded, injectable RNG owned by the engine, so that:

- checkpoint snapshots and resume are reproducible (the seed is part of the checkpoint),
- audited tests pin outcomes deterministically through one surface,
- the harness drives or asserts random outcomes without per-card hacks.
## Decisions

- **Checkpoints are blessed by the reference harness**, never self-eval. [SETTLED — 2026-06-10]
- **Grouping is predefined and stable** (not model-chosen), along a capability DAG — foundational mechanics before dependent cards — with a secondary size cap. [SETTLED — 2026-06-10]
- **Single engine-owned seeded RNG** for all random effects. [SETTLED — 2026-06-10]
- **Who authors the capability DAG** (oracle authors?); capability-layered vs fixed-size grouping balance. [OPEN]
- **Frozen vs revisable engine between checkpoints** — exact re-baseline semantics. [OPEN]
- **Granularity** — checkpoint count vs overhead and attribution coarseness. [OPEN]
- **Visibility** — runner/eval construct only, or also a prompting boundary the model is told about (Goal 3 implies the latter). [OPEN]
- **Dependency leakage** — the DAG must guarantee each step is solvable using only prior checkpoints' capabilities. [OPEN]
