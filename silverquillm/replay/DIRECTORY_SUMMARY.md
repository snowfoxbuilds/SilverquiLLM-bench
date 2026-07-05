# Directory Summary — `silverquillm/replay/`

## Overview

- **Responsibility**: 17lands GRE replay data parser, executor, and validation pipeline. Parses pre-parsed GRE message streams from 17lands replay exports into structured game objects, then validates the SilverquiLLM engine's behavior against real Arena game state snapshots.
- **The "Why"**: Provides ground-truth validation by replaying actual MTG Arena games through the engine and detecting where engine behavior diverges from the official game client.
- **Dependencies**:
  - Upstream: `engine/` (game engine for replay execution), `data/replays/` (card ID map, sample replays)
  - Downstream: `silverquillm/cli.py` (registers `validate` subcommand)

## Core Components & Symbols

| File | Lines | Responsibility | Key Exports |
|------|-------|---------------|-------------|
| `__init__.py` | 38 | Package init with public API exports. | `parse_replay`, `ReplayGame`, `GameSnapshot`, `ReplayAction`, `PlayerInfo`, `ReplayExecutor`, `StateMismatch`, `StepResult`, `Divergence`, `DivergenceType`, `ValidatingExecutor`, `ValidationReport`, `validate_replay` |
| `types.py` | 221 | Data types for replay parsing. | `PlayerInfo`, `TurnInfo`, `GameObject`, `Zone`, `Annotation`, `ReplayAction`, `GameInfo`, `GameSnapshot`, `ReplayGame` |
| `state.py` | 413 | GRE state reconstruction — full/diff game state message merging with sparse gameObject merge, action inference from annotations, `ObjectTracker` for zone transition tracking. | `build_game_info()`, `build_turn_info()`, `apply_full_state()`, `apply_diff()`, `extract_object_id_changes()`, `infer_actions()`, `ObjectTracker` |
| `parser.py` | 179 | High-level `parse_replay()` function. Loads card ID map, iterates raw JSON messages, delegates to `state.py` for reconstruction, produces `ReplayGame`. | `parse_replay()`, `load_card_id_map()` |
| `executor.py` | 840 | `ReplayExecutor` — steps through `GameSnapshot` objects and validates engine behavior via state-diff comparison. Seat 1 (17lands user) gets full validation; Seat 2 (opponent) uses oracle injection. | `ReplayExecutor`, `StateMismatch`, `StepResult`, `load_card_id_map()` |
| `validation.py` | 392 | Divergence detection and reporting. Records structured divergences when the engine can't execute a replay action or produces different state. Produces `ValidationReport` with summary statistics. | `DivergenceType`, `Divergence`, `ValidationReport`, `ValidatingExecutor`, `validate_replay()` |
| `cli.py` | ~400 | CLI `validate` subcommand — file/directory replay validation with `--cards`, `--verbose`, `--report`, `--stop-on-divergence`, `--benchmark`, `--workspace`, `--card-set`, `--simulate`. Resolves which workspace to import (explicit `--workspace` wins over `--benchmark`), builds its card registry via the workspace's own `cards.loader`, and aggregates results across multiple replay files. | `validate` (Click command) |

## Architecture & Patterns

- **Pipeline**: Raw JSON → `parse_replay()` → `ReplayGame` → `ReplayExecutor`/`ValidatingExecutor` → `ValidationReport`
- **Registry is what makes validation real**: with no registry every card is a generic `CardImpl` placeholder and *nothing diverges*. `cli.py` resolves a workspace (`--workspace`, or `--benchmark <id>` → `benchmarks/<id>/workspace`), imports that workspace's own `cards.loader` to build the registry (the workspace owns its card pool — its tests and agent harnesses build the same registry), and passes it to `ReplayExecutor`. For MSH the card set is `fdn` (replays are FDN-format). SOS gets no registry, preserving its frozen scripted-player path.
- **Caveat — swallowed failures (observer mode)**: when a registered card's ability resolution raises in observer mode, the executor logs `Ability engine resolution failed …` and applies a snapshot/life-delta fallback rather than recording a divergence, so impl bugs (e.g. a `NameError` in a trigger) appear only in logs, not in the report's divergence count. Simulate mode records these as `ENGINE_ERROR` divergences instead.
- **State reconstruction**: GRE messages come as Full or Diff; `apply_full_state()` builds complete snapshots, `apply_diff()` merges sparse updates into previous state.
- **Two execution modes**: default **observer mode** (state mirroring with pre-compare sync — the frozen SOS behavior) and **simulate mode** (`--simulate`, MSH): gameplay is driven through the engine — `cast_spell` with GRE-derived target Intents and ManaPaid-funded mana (pool credited by look-ahead, taps land at the annotation's home snapshot), `play_land`, flashback-style casts via `cast_spell_free` from graveyard/exile, activated abilities via `activate_ability` (single-ability sources), engine combat from `attackState`/`blockState` walking the GRE damage-step sequence (separate first-strike/normal passes), multi-blocker damage order answered from observed deaths, turn-structure events (upkeep/begin-combat/end-step) fired at GRE step boundaries plus a replay-side cleanup at the turn boundary, mulligan-aware draws through the engine library — then state is compared BEFORE an oracle resync, so each step validates independently.
- **Dual-seat model**: Seat 1 (17lands user) is fully validated against engine; Seat 2 (opponent) actions are injected as oracle data (observer mode) or run through the engine once GRE reveals them (simulate mode). Hidden-origin plays (opponent casts/land plays, whose pre-move object never appears in the prior snapshot) are synthesized from the arrival side by `_infer_hidden_origin_actions`.
- **Divergence types**: `MISSING_CARD` (card not in engine registry), `STATE_MISMATCH` (engine state differs from GRE), `ILLEGAL_ACTION` (engine rejects valid Arena action), `ENGINE_ERROR` (engine raises exception / API fallback in simulate mode), `QUERY_UNANSWERED` / `PROTOCOL_ERROR` (MSH Player Query protocol failures).
- **Diff semantics**: GRE diffs re-send **complete** objects with protobuf default-omission — `apply_diff` replaces gameObjects (a re-sent permanent without `isTapped` is untapped).
- **ObjectTracker**: Tracks GRE `objectId` changes across zone transitions via `ObjectIdChanged` annotations.

## Developer Guide & Constraints

- **Entry Points**: Start with `parser.py` → `parse_replay()` for understanding the data flow, then `executor.py` → `ReplayExecutor` for engine integration.
- **Extension**: Add new action types in `state.py` → `infer_actions()`. Add new divergence checks in `validation.py` → `ValidatingExecutor`.
- **Constraints**:
  - Card ID map (`data/replays/card_id_map.json`) must be kept in sync when new cards are added; use `scripts/build_card_id_map.py` to regenerate.
  - `GameSnapshot` objects are immutable once created — state reconstruction creates new copies.
  - `ReplayExecutor` expects snapshots in chronological order.

## Directory Structure

```
silverquillm/replay/
├── __init__.py          — Public API exports
├── types.py             — Dataclasses: ReplayGame, GameSnapshot, ReplayAction, GameObject, etc.
├── state.py             — GRE state reconstruction (full/diff merge, action inference, ObjectTracker)
├── parser.py            — High-level parse_replay() function
├── executor.py          — ReplayExecutor (state-diff observer mode)
├── validation.py        — DivergenceType, Divergence, ValidationReport, ValidatingExecutor, validate_replay
└── cli.py               — CLI `validate` subcommand
```
