Status: ACCEPTED

Date: 2026-05-08

## Context

The benchmark runner processes multiple cards sequentially per agent run. The original design assumed isolated workspaces per card — each card starts from a clean engine copy. However, target set cards (SOS) require mechanics not in the base engine (e.g., Ward, Magecraft). Agents need to extend the engine to implement these cards.

## Decision

A single benchmark run uses a **persistent, writable engine** that accumulates the agent's modifications across cards. Each run starts from the same base engine, so different agents are comparable.

**Per-run lifecycle:**

1. Run starts → copy `engine/` to a persistent run-level directory
2. Card N workspace gets the engine as modified by cards 1 through N-1
3. Agent implements card N → may modify engine files
4. Engine changes committed back to the run-level copy
5. All previous cards' tests re-run (regression check)
6. Repeat for all cards
## Trade-offs

**Gains:**

- Measures architectural quality — good agents write generic mechanics that benefit future cards
- Measures forward thinking — agents that write one-off hacks get penalized by regressions
- More realistic — real developers extend shared codebases incrementally
- Enables Category 4 scoring (Engine Extension Quality)
**Costs:**

- Card ordering affects results — earlier cards shape the engine for later ones
- A bad engine change early can cascade failures (mitigated by regression checks)
- Harder to parallelize runs (cards must be sequential within a run)
- Debugging is harder — failures may come from engine changes made several cards ago
## Alternatives Considered

- **Isolated workspaces**: Each card gets a clean engine. Simpler, parallelizable, but can't measure engine extension quality or forward thinking. Agents would re-implement the same mechanic for every card that needs it.
- **Checkpoint + rollback**: Persistent engine but rollback on regression. Rejected because the penalty for regressions is itself a useful signal.
## Consequences

- Cards sorted by complexity tier (trivial → expert) so agents build up capabilities gradually
- Regression test runner is mandatory infrastructure
- Engine diffs captured per card for Category 4 scoring
- Each agent/model gets its own run — no cross-agent engine contamination
