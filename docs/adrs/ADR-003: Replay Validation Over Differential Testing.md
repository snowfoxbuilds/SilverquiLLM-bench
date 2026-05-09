Status: ACCEPTED

Date: 2026-05-08

## Context

The engine is a Python port of XMage (Java). The original [TEST-SUITE.md](http://test-suite.md/) spec planned **Differential Testing** as the primary engine correctness check: convert tests to engine-agnostic JSON, execute in both Python and XMage via a Java adapter, and compare final states.

## Decision

Replace XMage differential testing with **Replay Validation**: replay recorded MTGA game states (sourced from 17lands GRE message exports) through the Python engine and verify full game state at every GRE message boundary matches the recorded state.

## Rationale

1. **MTGA is closer to ground truth than XMage** — MTGA is Wizards of the Coast's own rules implementation. XMage is a community project that can have bugs.
2. **Cross-language comparison is costly** — Translating between Java and Python state representations adds complexity without adding confidence. Discrepancies could mean bugs in either engine or in the translation layer.
3. **17lands provides massive scale** — Thousands of real limited games with full GRE state streams, covering natural gameplay patterns that hand-written tests can't match.
4. **FDN limited is the validation target** — 17lands has extensive Foundations limited data, which maps directly to the Base Set (FDN 001–291).
## Data Format

17lands replay data is **pre-parsed GRE (Game Rules Engine) JSON** — not aggregate CSV or raw MTGA logs. Each file contains the full game state stream for one game:

- Top-level: `{seat_id, opponent_seat_id, events: [...]}`
- Each event is a `GameStateMessage` with explicit `GameStateType_Full` or `GameStateType_Diff` flag
- Full state includes: `gameInfo`, `players` (life totals), `turnInfo` (phase/step/turn), `zones` (with object lists), `gameObjects` (cards with `grpId`, types, P/T, tap state), `annotations` (zone transfers, damage, etc.)
- Diffs are incremental: merge zones by `zoneId`, upsert `gameObjects` by `instanceId`, purge `diffDeletedInstanceIds`
- Card identity tracked via `grpId` → card name mapping (from 17lands card list)
- Object identity tracked via `instanceId`, with `AnnotationType_ObjectIdChanged` recording zone-transfer ID changes
See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) for the full schema documentation.

## Execution Model: Observer Mode

The executor operates in **observer mode** using state-diff comparison:

1. Parse GRE stream into a sequence of `GameSnapshot` objects (reconstructed full state at each `gameStateId`)
2. For each consecutive pair of snapshots, diff zones/objects to extract what changed (the "action")
3. **Seat 1 (17lands user):** Full validation — we have complete information (hand contents, draws, plays). Verify the engine processes the action correctly.
4. **Seat 2 (opponent):** Oracle injection — we see what they played (public game objects on battlefield/stack) but not their hidden hand. Inject their actions directly into the engine state without validating legality from their hand.
5. After each action, compare the engine's resulting state against the next GRE snapshot.
6. Record divergences with `gameStateId`, expected vs actual state.
This validates the engine's **rules processing** (state transitions, triggered abilities, combat resolution) without requiring full information about both players.

## Trade-offs

**Gains:**

- Validates against the authoritative rules implementation (MTGA)
- **Full state comparison at every GRE message boundary** — not just EOT checkpoints
- **Object-level tracking** — specific cards with `grpId`, not aggregate counts
- **Single data source, single parser** — clean JSON, no format auto-detection
- Covers real gameplay patterns at scale (thousands of games)
- No Java adapter needed — simpler infrastructure
- Tests natural game flows, not just isolated card interactions
**Costs:**

- MTGA also has bugs and timing shortcuts — discrepancies may not always mean the Python engine is wrong
- Opponent's hidden information (hand, library order) is not available — observer mode handles this via oracle injection
- `grpId` → card name mapping required (from 17lands card list files)
- Replay Validation pipeline must be built (deferred until all 291 FDN cards are implemented)
## Alternatives Considered

- **XMage Differential Testing** (original plan): Full state comparison via Java adapter. Rejected — cross-language complexity, XMage can have bugs, and XMage is the porting source not the correctness oracle.
- **Manual test-only validation**: Rely solely on hand-written unit tests. Insufficient coverage for 291 cards.
- **MTGA API integration**: Query MTGA directly for rule adjudication. Not feasible — MTGA has no public rules API.
## Consequences

- Differential Testing section in [TEST-SUITE.md](http://test-suite.md/) replaced with Replay Validation section
- Replay Validation pipeline is a Future Work item, blocked on FDN 001–291 + SPG 74–83 completion
- 17lands GRE JSON data provided — schema documented in [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8)
- First benchmark runs proceed as Pipeline Validation Runs (no Replay Validation yet)
- XMage remains the porting reference for engine structure, but not the correctness oracle
- Only one parser needed (17lands GRE JSON) — no CSV or raw MTGA log parsing
