# SilverquiLLM-bench

LLM benchmark that evaluates coding ability by tasking models with implementing Magic: The Gathering cards as Python classes in a custom game engine. Uses cards from the newest MTG set (not yet in training data) to minimize contamination. Python package name: `silverquillm`.

## Conventions

- Language: Python ≥3.12
- Engine: Python port of XMage (Java, MIT)
- Base set: FDN Draft Set (301 cards: FDN 001–291 + SPG 074–083) — used as in-context examples
- Benchmark set: SOS Draft Set (346 cards: SOS ≤271 + SOA 1–65 + SPG 149–158, released 2026-04-24) — benchmark targets
- Agents: Docker-based black-box containers (one image per agent+mode+strategy variant)
- License: MIT (matching XMage)
- Card implementations: one class per card, subclassing `CardImpl`
- Tests: pytest with `test_utils` helpers, max 30 per card. Run with `--ignore=tests/audited/` unless working on card implementations specifically. 
- Three evaluation dimensions: SOS card correctness, FDN card regression, engine regression
- Development phases: Phase 1 (engine port) → Phase 2 (container harness + audited tests) → Phase 3 (FDN completion + replay validation) → Phase 4 (SOS benchmark runs + leaderboard)
## Domain Language

See [CONTEXT.md](https://www.notion.so/3a3e1d4cf0384c3cb2735ae280b71918) for the project's domain glossary.

All specs, code, and agent instructions use these terms exactly.

## Architecture Summary

The benchmark runner stages a Workspace (engine, rulebook, FDN examples, SOS templates, prompt), launches a Docker container, waits for it to exit, materializes `workspace_final/`, and evaluates the results. The Docker image IS the full agent configuration — it bakes in the agent CLI, mode (blind/tested), strategy, model, and prompt. The runner passes only workspace/output volumes, API keys, and a timeout.

Three evaluation dimensions (all post-run, audited tests only):

1. **SOS Card Correctness** — Audited SOS tests against agent's `card_impl.py` + harvested `/workspace/engine/`
2. **FDN Card Regression** — Audited FDN tests against pre-filled FDN impls + harvested `/workspace/engine/`
3. **Engine Regression** — Core engine tests (`tests/engine/`) against harvested `/workspace/engine/`
Agent-written tests are harvested as artifacts but not scored in v1. Cross-eval and test quality scoring deferred to v2 (test harvester).

## Specs

| File | Summary |
| --- | --- |
| `PROJECT-OVERVIEW.md` | Project purpose, scope, development phases, and key decisions |
| `GAME-ENGINE.md` | Python port of XMage rules engine, core systems, and game state API |
| `CARD-INTERFACE.md` | Card class hierarchy, hook methods, and supporting types |
| `TEST-SUITE.md` | Test structure, test utilities API, audited test path, test harvester (v2) |
| `BENCHMARK-RUNNER.md` | Host-side orchestrator: workspace staging, container launch, result harvesting, evaluation |
| `SCORING.md` | Three evaluation dimensions, complexity weighting, leaderboard format |
| `AGENT-CONTAINERS.md` | Docker black-box architecture, file-based contract, entrypoint design, isolation guarantees |
| `WORKSPACE-CONTRACT.md` | Workspace layout, card directory invariant, Run Manifest, writable engine, FDN/SOS structure |
| `RUN-ARTIFACTS-AND-TELEMETRY.md` | workspace_final, Git snapshots, fallback, telemetry, Docker logs, filtered runs, smoke runs |
| `TESTING-CONVENTIONS.md` | Test naming, fixtures, assertions, and conventions for audited tests |
| `17LANDS-REPLAY-SCHEMA.md` | GRE JSON replay format for engine correctness validation |

## ADRs

Architectural decisions are documented under the ADRs page:

| ADR | Summary |
| --- | --- |
| `ADR-003` | Replay Validation over differential testing — 17lands GRE JSON, observer mode, full state-diff comparison |
| `ADR-004` | Docker Agent Containers replace Python adapters — image is full agent config; runner stages, launches, harvests, evaluates |
| `ADR-005` | In-place Workspace engine with Git snapshot fallback — agent edits `/workspace/engine/`; runner evaluates `workspace_final/` |

## Harness Structure

```javascript
silverquillm/
  cli.py              # arg parsing + docker run + harvest
  card_loader.py      # card spec loading
  evaluator.py        # post-harvest test runner (3 dimensions)
  results.py          # run_summary.json generation
  workspace.py        # stage_workspace()
docker/
  pi-blind/
    Dockerfile
    entrypoint.sh
    models.json
  pi-tested/
    Dockerfile
    entrypoint.sh
    models.json
  opencode-tested/
    Dockerfile
    entrypoint.sh
  opencode-blind/
    Dockerfile
    entrypoint.sh
tests/
  audited/
    fdn/{collector_number}/tests.py
    sos/{collector_number}/tests.py
  engine/             # Core engine regression tests
```
