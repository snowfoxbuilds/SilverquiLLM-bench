Status: ACCEPTED

Date: 2026-05-08

## Context

The engine is a Python port of XMage (Java). The original [TEST-SUITE.md](http://test-suite.md/) spec planned **Differential Testing** as the primary engine correctness check: convert tests to engine-agnostic JSON, execute in both Python and XMage via a Java adapter, and compare final states.

## Decision

Replace XMage differential testing with **Replay Validation**: replay recorded MTGA game actions (sourced from 17lands) through the Python engine and verify game-state checkpoints (life totals, board state, winner) match the recorded outcomes.

## Rationale

1. **MTGA is closer to ground truth than XMage** — MTGA is Wizards of the Coast's own rules implementation. XMage is a community project that can have bugs.
2. **Cross-language comparison is costly** — Translating between Java and Python state representations adds complexity without adding confidence. Discrepancies could mean bugs in either engine or in the translation layer.
3. **17lands provides massive scale** — Thousands of real limited games with full action logs, covering natural gameplay patterns that hand-written tests can't match.
4. **FDN limited is the validation target** — 17lands has extensive Foundations limited data, which maps directly to the Base Set (FDN 001–291).
## Trade-offs

**Gains:**

- Validates against the authoritative rules implementation (MTGA)
- Covers real gameplay patterns at scale (thousands of games)
- No Java adapter needed — simpler infrastructure
- Tests natural game flows, not just isolated card interactions
**Costs:**

- Weaker guarantee than full state-matching — only checks game-state checkpoints, not every intermediate state
- MTGA also has bugs and timing shortcuts — discrepancies may not always mean the Python engine is wrong
- 17lands data requires parsing and translation into `DeterministicPlayer` action sequences
- Replay Validation pipeline must be built (deferred until all 291 FDN cards are implemented)
## Alternatives Considered

- **XMage Differential Testing** (original plan): Full state comparison via Java adapter. Rejected — cross-language complexity, XMage can have bugs, and XMage is the porting source not the correctness oracle.
- **Manual test-only validation**: Rely solely on hand-written unit tests. Insufficient coverage for 291 cards.
- **MTGA API integration**: Query MTGA directly for rule adjudication. Not feasible — MTGA has no public rules API.
## Consequences

- Differential Testing section in [TEST-SUITE.md](http://test-suite.md/) replaced with Replay Validation section
- Replay Validation pipeline is a Future Work item, blocked on FDN 001–291 completion
- Sean provides 17lands data when the Base Set is ready
- First benchmark runs proceed as Pipeline Validation Runs (no Replay Validation yet)
- XMage remains the porting reference for engine structure, but not the correctness oracle
