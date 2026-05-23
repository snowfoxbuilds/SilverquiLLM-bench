# SilverquiLLM-bench

A benchmark for evaluating LLM coding agents by tasking them with implementing **Magic: The Gathering** cards as Python classes in a custom game engine.

SilverquiLLM-bench uses cards from a newly released MTG set to reduce training-data contamination and measure genuine code-generation ability: reading specs, understanding rules text, extending an engine, and producing working implementations.

---

## Why MTG Cards?

Magic cards are useful coding benchmark tasks because they:

- **Span a wide difficulty range** — from vanilla creatures to complex cards with multiple interacting abilities
- **Translate natural language into code** — rules text must become executable behavior
- **Test architecture** — agents often need reusable engine extensions, not one-off hacks
- **Have clear correctness signals** — card behavior is testable with deterministic game states
- **Resist memorization** — new sets introduce new mechanics and fresh card text

---

## Current Benchmark Set

**Secrets of Strixhaven (SOS)** — released 2026-04-24

| Subset | Cards |
| --- | --- |
| SOS Base Set | 271 |
| SOA Mystical Archives | 65 |
| SPG Special Guests | 10 |
| **Total** | **346** |

Cards are classified into five complexity tiers:

```
trivial → simple → medium → complex → expert
```

Complexity is based on rules text, keyword count, ability count, card type, target requirements, and zone interactions.

---

## How It Works

```
Stage Workspace → Run Agent Container → Snapshot Progress → Harvest workspace_final → Evaluate
```

1. **Stage Workspace**
    - The runner creates a codebase-shaped Workspace with:
        - FDN reference examples
        - SOS target templates
        - editable engine source
        - rulebook and API docs
        - prompt and run manifest
2. **Run Agent Container**
    - The Docker image is the full agent configuration.
    - The runner launches one container for the whole run.
    - The agent edits `/workspace/engine/` and `cards/sos/{card_id}/card_impl.py` in place.
3. **Snapshot Progress**
    - Every 60 seconds, the runner commits the full Workspace to a host-side Git snapshot repo.
    - Snapshots support progress telemetry and recovery from corrupted final engine state.
4. **Harvest Final Workspace**
    - The official evaluation state is materialized as:

```
docker/<image_dir>/results/<run_name>/workspace_final/
```

> **`<image_dir>` derivation**: Derived from the `--image` flag by stripping the `silverquillm-` prefix and `:tag` suffix. For example, `silverquillm-local-pi-blind:latest` → `local-pi-blind`.

1. **Evaluate**
    - Evaluation is post-run and reads only from `workspace_final/`.

---

## Evaluation Dimensions

SilverquiLLM-bench reports three independent evaluation dimensions.

| Dimension | What it measures |
| --- | --- |
| **SOS Card Correctness** | Whether target SOS card implementations pass audited SOS tests |
| **FDN Card Regression** | Whether the agent's engine changes broke filled FDN reference cards |
| **Engine Regression** | Whether the agent's engine changes broke core game mechanics |

Agent-written tests are harvested as artifacts but are not scored in v1. Self-eval, cross-eval, and test-quality scoring are deferred to a future test harvester.

---

## Workspace Contract

The Workspace is the only evaluatable state an Agent Container can produce.

Canonical layout:

```
/workspace/
  prompt.md
  run_manifest.json
  rulebook.md
  engine_api.md
  base_classes.py
  test_utils.md
  engine/
  cards/
    fdn/
      {card_id}/
        card_spec.json
        card_impl.py
    sos/
      {card_id}/
        card_spec.json
        card_impl.py
        tests.py        # optional, agent-written in Tested Mode
```

Hard rules:

- Each card's canonical implementation class must be importable from:

```
cards/{set}/{card_id}/card_impl.py
```

- Agents must not move or rename card directories.
- FDN examples and SOS targets use the same card directory shape.
- Agents edit `/workspace/engine/` in place.
- There is no separate `engine_work/`.
- `/output/` is telemetry-only and never required for evaluation.

### Run Manifest

Immediately before container launch, the runner writes:

```json
{
  "timeout_seconds": 7200,
  "deadline_utc": "2026-05-13T22:22:00Z"
}
```

This is advisory runtime context only. It is not agent configuration.

---

## Project Structure

```
engine/                         Core MTG rules engine
  game.py                       Game helpers and orchestration
  turn.py                       Turn, phase, and step progression
  card.py                       CardImpl base classes
  casting.py                    Casting, targets, costs, resolution
  combat.py                     Combat phases and damage
  stack.py                      Spell/ability stack
  mana.py                       Mana costs and payment
  zones.py                      Zone containers and movement
  continuous_effects.py         Layer system
  replacement_effects.py        Replacement effects
  state_based_actions.py        State-based actions
  protection.py                 Protection checks

cards/
  registry.py                   Card registry and metadata
  scryfall.py                   Scryfall helpers/cache
  fdn/                          FDN reference examples
    {card_id}/
      card_spec.json
      card_impl.py
  sos/                          SOS benchmark targets
    {card_id}/
      card_spec.json
      card_impl.py

silverquillm/                   Benchmark runner package
  cli.py                        CLI entry point
  workspace.py                  Workspace staging
  evaluator.py                  Post-run evaluation
  results.py                    run_summary.json generation
  card_loader.py                Card spec loading
  replay/                       17lands replay validation

docker/                         Agent container images
  pi-blind/
  pi-tested/
  opencode-blind/
  opencode-tested/

tests/
  engine/                       Core engine regression tests
  audited/fdn/                  FDN audited regression tests
  audited/sos/                  SOS audited correctness tests

docs/                           Specs, generated docs, references
```

---

## Runner Artifacts

Each run writes a self-contained results directory.

```
docker/<image_dir>/results/<run_name>/
  workspace_final/              Official evaluation Workspace
  snapshots/                    Host-side Git Workspace snapshots
  snapshot_telemetry.jsonl      Filesystem-based progress telemetry
  docker_stdout.log             Docker stdout captured by runner
  docker_stderr.log             Docker stderr captured by runner
  engine_diff.patch             Diff vs. host baseline engine
  run_summary.json              Canonical machine-readable report
  cards/                        Optional derived convenience artifacts
```

### Snapshot fallback

If final engine state is unusable, the runner may walk snapshots backward and select the latest whole-Workspace snapshot whose engine passes:

```
tests/engine/
```

Fallback uses the entire selected Workspace snapshot. The runner does not combine final card implementations with an earlier engine snapshot.

If no snapshot is viable, the run is marked:

```
no_viable_output_produced
```

---

## Quickstart

### Prerequisites

- Python ≥ 3.12
- Docker
- An agent image, such as:
    - `silverquillm-pi-blind:latest`
    - `silverquillm-pi-tested:latest`
    - `silverquillm-opencode-blind:latest`
    - `silverquillm-opencode-tested:latest`

### Install

```bash
git clone https://github.com/snowfoxbuilds/SilverquiLLM-bench.git
cd SilverquiLLM-bench
pip install -e ".[dev]"
```

### Build an agent image

```bash
docker build -t silverquillm-pi-blind:latest docker/pi-blind/
docker build -t silverquillm-pi-tested:latest docker/pi-tested/
```

### Smoke test an image

```bash
silverquillm smoke --image silverquillm-pi-blind:latest
```

Smoke runs are container-validation only. They use a tiny synthetic Workspace and do not enter benchmark summaries or leaderboards.

### Run a benchmark

```bash
silverquillm run \
  --image silverquillm-pi-blind:latest \
  --timeout 7200
```

### Run a development subset

```bash
silverquillm run \
  --image silverquillm-pi-blind:latest \
  --cards 001,042,105 \
  --timeout 3600
```

Filtered runs are for development and pipeline validation only. They are not leaderboard-valid.

---

## Scoring and Leaderboards

Leaderboard-valid runs require:

- full SOS Draft Set staged
- `card_filter = null`
- successful evaluatable `workspace_final/`

Filtered runs, smoke runs, and `no_viable_output_produced` runs are excluded from leaderboards by default.

SOS Card Correctness can be complexity-weighted. FDN Card Regression and Engine Regression are reported separately rather than folded into a single composite score.

---

## Game Engine

The engine implements core MTG rules for two-player games:

- turn structure
- stack and priority
- spell casting and resolution
- combat
- mana payment
- zones
- card types and subtypes
- triggered abilities
- replacement effects
- continuous effects and layers
- state-based actions
- protection
- extra turns

Card implementations subclass `CardImpl` or type-specific classes such as `Creature`, `Instant`, `Sorcery`, `Artifact`, `Enchantment`, `Planeswalker`, and `Land`.

---

## Replay Validation

The replay validation pipeline parses 17lands GRE replay data and validates engine behavior against reconstructed MTG Arena game state streams.

Key ideas:

- 17lands replay JSON contains full and diff GRE game state messages.
- Seat 1 is fully validated.
- Seat 2 uses oracle-injected public actions where hidden information is unavailable.
- The engine is compared against reconstructed game state at GRE message boundaries.

Replay Validation is for validating the FDN base engine before scored benchmark runs.

---

## Contamination Controls

- **New target set** — SOS released 2026-04-24.
- **Container isolation** — agents see only the staged Workspace.
- **Audited tests excluded** — audited tests are never mounted into the agent container.
- **No cross-agent leakage** — each run gets its own fresh Workspace and container.
- **Workspace snapshots are host-side** — `.git` snapshot history is not mounted into the container.
- **FDN examples are intentional** — FDN implementations are reference examples, not contamination.

---

## Logs and Telemetry

`/output/` is optional telemetry only. It may contain:

```
/output/
  progress.jsonl
  system.log
  agent_stdout.log
  agent_stderr.log
  exit_code
```

The runner must tolerate `/output/` being empty.

The runner independently captures Docker stdout/stderr:

```
docker/<image_dir>/results/<run_name>/docker_stdout.log
docker/<image_dir>/results/<run_name>/docker_stderr.log
```

Live terminal logs are labeled and colorized by type when running in an interactive terminal. Use:

```bash
--color auto
--color always
--color never
```

---

## Running Tests

```bash
# All tests
pytest

# Engine tests
pytest tests/engine/

# FDN audited regression tests
pytest tests/audited/fdn/

# SOS audited correctness tests
pytest tests/audited/sos/

# Integration tests
pytest -m integration
```

Testing conventions:

- no real `os.kill*()` or signal calls in unit tests
- explicit fake PIDs for mocks
- no infinite loops or long sleeps
- no open-ended `game.run()` in unit tests
- mock subprocesses in unit tests
- use `pytest-timeout` safety limits

---

## Documentation

Important specs:

- `PROJECT-OVERVIEW.md`
- `GAME-ENGINE.md`
- `CARD-INTERFACE.md`
- `TEST-SUITE.md`
- `BENCHMARK-RUNNER.md`
- `AGENT-CONTAINERS.md`
- `WORKSPACE-CONTRACT.md`
- `RUN-ARTIFACTS-AND-TELEMETRY.md`
- `SCORING.md`
- `TESTING-CONVENTIONS.md`
- `17LANDS-REPLAY-SCHEMA.md`

Important ADRs:

- ADR-003 — Replay Validation over differential testing
- ADR-004 — Docker Agent Containers replace Python adapters
- ADR-005 — In-place Workspace engine with snapshot fallback

---

## Acknowledgments

The game engine is inspired by [XMage](https://github.com/magefree/mage), an open-source Magic: The Gathering simulator.

## License

MIT — see [LICENSE](LICENSE) for details.