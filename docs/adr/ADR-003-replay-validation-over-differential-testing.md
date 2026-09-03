Status: ACCEPTED

Date: 2026-05-08

# ADR-003: Replay Validation Over Differential Testing

## Context

The engine is a Python port of XMage (Java). The original [AUDITED-TEST-SUITE.md](../specs/AUDITED-TEST-SUITE.md) spec planned **Differential Testing** as the primary engine correctness check: convert tests to engine-agnostic JSON, execute in both Python and XMage via a Java adapter, and compare final states.

## Decision

Replace XMage differential testing with **Replay Validation**: replay recorded MTGA game states (sourced from 17lands GRE message exports) through the Python engine and verify full game state at every GRE message boundary matches the recorded state.

The reasoning:

1. **MTGA is closer to ground truth than XMage** — MTGA is Wizards of the Coast's own rules implementation. XMage is a community project that can have bugs.
2. **Cross-language comparison is costly** — translating between Java and Python state representations adds complexity without adding confidence; a discrepancy could mean a bug in either engine or in the translation layer.
3. **17lands provides massive scale** — thousands of real limited games with full GRE state streams, covering natural gameplay patterns hand-written tests can't match.
4. **FDN limited is the validation target** — 17lands has extensive Foundations limited data, which maps directly to the Base Set (FDN 001–291).

## Data Format

17lands replay data is **pre-parsed GRE (Game Rules Engine) JSON** — not aggregate CSV or raw MTGA logs. Each file contains the full game state stream for one game: a top-level `{seat_id, opponent_seat_id, events: [...]}` where each event is a `GameStateMessage` flagged full or diff. Full state carries `gameInfo`, `players`, `turnInfo`, `zones`, `gameObjects`, and `annotations`; diffs merge incrementally; card and object identity track via `grpId` and `instanceId`. See [17lands Replay Data Schema](../specs/17LANDS-REPLAY-SCHEMA.md) for the full schema.

## Execution Model: Observer Mode

The executor operates in **observer mode** using state-diff comparison:

1. Parse the GRE stream into a sequence of `GameSnapshot` objects (reconstructed full state at each `gameStateId`).
2. For each consecutive pair of snapshots, diff zones/objects to extract what changed (the "action").
3. **Seat 1 (17lands user):** full validation — complete information (hand contents, draws, plays), so verify the engine processes the action correctly.
4. **Seat 2 (opponent):** oracle injection — public game objects are visible but not the hidden hand, so inject their actions directly without validating legality from their hand.
5. After each action, compare the engine's resulting state against the next GRE snapshot.
6. Record divergences with `gameStateId`, expected vs actual state.

This validates the engine's **rules processing** (state transitions, triggered abilities, combat resolution) without requiring full information about both players.

## Consequences

- **Positive**: Validates against the authoritative rules implementation (MTGA), with full state comparison at every GRE message boundary — not just EOT checkpoints — and object-level tracking of specific cards by `grpId`, not aggregate counts.
- **Positive**: A single data source and single parser — clean JSON, no format auto-detection, no Java adapter to build or maintain.
- **Positive**: Covers real gameplay patterns at scale (thousands of games), testing natural game flows rather than isolated card interactions.
- **Negative**: MTGA also has bugs and timing shortcuts, so a discrepancy does not always mean the Python engine is wrong.
- **Negative**: Opponent hidden information (hand, library order) is unavailable; observer mode handles this via oracle injection.
- **Negative**: Requires a `grpId` → card-name mapping (from 17lands card list files), and the Replay Validation pipeline must be built (deferred until all 291 FDN cards plus SPG 74–83 are implemented).
- **Neutral**: The Differential Testing section in [AUDITED-TEST-SUITE.md](../specs/AUDITED-TEST-SUITE.md) is replaced with a Replay Validation section; XMage remains the porting reference for engine structure, but not the correctness oracle.
- **Neutral**: First benchmark runs proceed as Pipeline Validation Runs, before any Replay Validation exists.

## Alternatives Considered

- **XMage Differential Testing** (original plan): full state comparison via a Java adapter. Rejected — cross-language complexity, XMage can have bugs, and XMage is the porting source, not the correctness oracle.
- **Manual test-only validation**: rely solely on hand-written unit tests. Rejected — insufficient coverage for 291 cards.
- **MTGA API integration**: query MTGA directly for rule adjudication. Rejected — not feasible; MTGA has no public rules API.
