Status: ACCEPTED

Date: 2026-05-08

## Context

SOS cards require mechanics not in the base engine (e.g., Ward, Magecraft). Agents need to extend the engine to implement these cards. The question is whether each card gets a fresh engine copy or whether modifications accumulate.

## Decision

A single benchmark run uses a **writable engine copy** that the agent modifies freely throughout the run. The entrypoint copies `engine/` to `engine_work/` before the agent starts. Each run starts from the same base engine, so different agents are comparable.

**Per-run lifecycle:**

1. Runner stages workspace with read-only `engine/`
2. Container entrypoint copies `engine/` to `engine_work/`
3. Agent implements all SOS cards, modifying `engine_work/` as needed
4. Runner harvests `engine_work/` and diffs against original
5. Evaluator runs FDN audited tests against the modified engine (FDN Regression check)
## Trade-offs

**Gains:**

- Measures architectural quality — good agents write generic mechanics that benefit future cards
- More realistic — real developers extend shared codebases incrementally
- Enables Category 4 scoring (Engine Extension Quality)
- Agent decides its own implementation order and strategy
**Costs:**

- No per-card regression attribution — only FDN tests detect engine breakage, and only post-run
- A bad engine change can silently affect many cards (detected only at evaluation time)
- Debugging is harder — only the final engine state is visible to the evaluator
## Alternatives Considered

- **Isolated workspaces**: Each card gets a clean engine. Simpler, but agents would re-implement the same mechanic for every card that needs it. Can't measure engine extension quality.
- **Checkpoint + rollback**: Persistent engine with per-card snapshots and rollback on regression. Rejected — adds complexity to the container model without proportional benefit. FDN regression check is sufficient.
## Consequences

- FDN audited tests (`tests/audited/fdn/`) serve as the regression suite against the final engine
- Engine diff captured as `engine_diff.patch` for Category 4 scoring
- Each agent/model gets its own run — no cross-agent engine contamination
- Agent manages its own card ordering within the container
