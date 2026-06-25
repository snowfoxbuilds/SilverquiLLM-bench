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
| `registry_loader.py` | 230 | Builds a `CardRegistry` from a chosen workspace's `cards/<set>/*/card_impl.py` so the replay exercises the *real* card implementations. Discovers subclass and `make_vanilla`-factory cards, folds in basic lands, skips unimplemented stubs, and reports coverage. | `build_registry()`, `RegistryLoadReport`, `ensure_workspace_on_path()` |
| `cli.py` | ~360 | CLI `validate` subcommand — file/directory replay validation with `--cards`, `--verbose`, `--report`, `--stop-on-divergence`, `--benchmark`, `--workspace`, `--card-set`. Resolves which workspace to import, builds its card registry, and aggregates results. | `validate` (Click command) |

## Architecture & Patterns

- **Pipeline**: Raw JSON → `parse_replay()` → `ReplayGame` → `ReplayExecutor`/`ValidatingExecutor` → `ValidationReport`
- **Registry is what makes validation real**: with no registry every card is a generic `CardImpl` placeholder and *nothing diverges*. `cli.py` resolves a workspace (`--workspace`, or `--benchmark <id>` → `benchmarks/<id>/workspace`), calls `registry_loader.build_registry()` to import that workspace's card impls, and passes the registry to `ReplayExecutor`. For MSH the card set is `fdn` (replays are FDN-format). SOS gets no registry, preserving its frozen scripted-player path.
- **Caveat — swallowed failures**: when a registered card's ability resolution raises, the executor logs `Ability engine resolution failed …` and applies a snapshot/life-delta fallback rather than recording a divergence, so impl bugs (e.g. a `NameError` in a trigger) appear only in logs, not in the report's divergence count.
- **State reconstruction**: GRE messages come as Full or Diff; `apply_full_state()` builds complete snapshots, `apply_diff()` merges sparse updates into previous state.
- **Dual-seat model**: Seat 1 (17lands user) is fully validated against engine; Seat 2 (opponent) actions are injected as oracle data since hidden information isn't available.
- **Divergence types**: `MISSING_CARD` (card not in engine registry), `STATE_MISMATCH` (engine state differs from GRE), `ILLEGAL_ACTION` (engine rejects valid Arena action), `ENGINE_ERROR` (engine raises exception).
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
