# SilverquiLLM-bench

LLM benchmark that evaluates coding ability by tasking models with implementing Magic: The Gathering cards as Python classes in a custom game engine. Uses cards from the newest MTG set (not yet in training data) to minimize contamination. Python package name: `silverquillm`.

## Conventions

- Language: Python ≥3.12
- Engine: Python port of XMage (Java, MIT)
- Base set: FDN Draft Set (301 cards: FDN 001–291 + SPG 074–083) — used as in-context examples
- Benchmark set: SOS Draft Set (271 cards: SOS 001–271, released 2026-04-24) — benchmark targets
- Agents: Docker-based black-box containers (one image per agent+mode+strategy variant)
- License: MIT (matching XMage)
- Card implementations: one class per card, subclassing `CardImpl`
- Tests: pytest with `test_utils` helpers, max 30 per card. Run with `--ignore=tests/audited/` unless working on card implementations specifically. 
- Three evaluation dimensions: target-set card correctness (SOS card correctness for SOS; HOB card correctness for the HOB generation), FDN card regression, engine regression
- Development phases: Phase 1 (engine port) → Phase 2 (container harness + audited tests) → Phase 3 (FDN completion + replay validation) → Phase 4 (SOS benchmark runs + leaderboard)
## Domain Language

See [CONTEXT.md](https://app.notion.com/p/3a3e1d4cf0384c3cb2735ae280b71918) for the project's domain glossary.

All specs, code, and agent instructions use these terms exactly.

## Architecture Summary

The benchmark runner stages a Workspace (engine, rulebook, FDN examples, SOS templates, prompt), launches a Docker container, waits for it to exit, materializes `workspace_final/`, and evaluates the results. The Docker image IS the full agent configuration — it bakes in the agent CLI, mode (blind/tested), strategy, model, and prompt. The runner passes only workspace/output volumes, API keys, and a timeout.

A Benchmark Run is one container session that consumes the benchmark's **entire** problem set in a single Workspace; the run spec is candidate + mode + benchmark + budget (per #39). Card-subset ("workload") runs are retired — cheap validation uses the dedicated smoke benchmark.

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
| `AUDITED-TEST-SUITE.md` | Test structure, test utilities API, audited test path, test harvester (v2) |
| `AUDITED-TEST-API.md` | The sanctioned test-only engine interface for audited tests: set up, host-side `priority_loop` / `advance_to_phase`, `DeterministicPlayer` directives, assertions; canonical-only, composes/duplicates canonical behavior, no workspace-engine changes |
| `BENCHMARK-RUNNER.md` | Host-side orchestrator: workspace staging, container launch, result harvesting, evaluation |
| `SCORING.md` | Three evaluation dimensions, complexity weighting, leaderboard format |
| `AGENT-CONTAINERS.md` | Docker black-box architecture, file-based contract, entrypoint design, isolation guarantees |
| `WORKSPACE-CONTRACT.md` | Workspace layout, card directory invariant, Run Manifest, writable engine, FDN/SOS structure |
| `RUN-ARTIFACTS-AND-TELEMETRY.md` | workspace_final, Git snapshots, fallback, telemetry, Docker logs, smoke runs (`silverquillm smoke` command vs. smoke benchmark) |
| `TESTING-CONVENTIONS.md` | Test naming, fixtures, assertions, and conventions for audited tests |
| `17LANDS-REPLAY-SCHEMA.md` | GRE JSON replay format for engine correctness validation |
| `AUDITED-TEST-IMPROVEMENT-WORKFLOW.md` | Harvest script + combined investigation/discovery skill (manual v1 Test Harvester); harvest format, fault-attribution triage, promotion bar, cadence, tier gating |
| `HOB-BENCHMARKS.md` | The three HOB-generation benchmarks (hob-easy/medium/hard): picked pools (23/5/5, selective subsets of the HOB set), run shape, engine freeze + tests-as-envelope, instruction docs, candidate contract |
| `DECISION-MODEL.md` | V2 engine Player Query / Player Decision protocol, Game Symbols/Refs, Intents, DeterministicPlayer (V2) (renamed from MSH-DECISION-MODEL.md — engine-level, pool-neutral) |

## ADRs

Architectural decisions are documented under the ADRs page:

| ADR | Summary |
| --- | --- |
| `ADR-003` | Replay Validation over differential testing — 17lands GRE JSON, observer mode, full state-diff comparison |
| `ADR-004` | Docker Agent Containers replace Python adapters — image is full agent config; runner stages, launches, harvests, evaluates |
| `ADR-005` | In-place Workspace engine with Git snapshot fallback — agent edits `/workspace/engine/`; runner evaluates `workspace_final/` |
| `ADR-006` | Engine tests staged into workspace — local regression loop for agents; grading still uses host copies; SOS/FDN tests stay hidden |
| `ADR-007` | Workspace as pre-built directory — wholesale `cp -r` from `benchmarks/sos/workspace/`; canonical engine source; collapses staging code and removes spec/code drift |
| `ADR-008` | Resume Legs are independent Benchmark Runs — `silverquillm resume <prior-run-id>` stages from prior `workspace_final/`; legs linked via `resumed_from`; prompt-layer owns resume detection |
| `ADR-009` | Resume reads prefer run-time artifacts over harvest-time artifacts — manifest + snapshot ledger over `run_summary.json`; resilient to partial harvester failure; ledger format now load-bearing |
| `ADR-010` | Test Oracle Workspace uses independent engine — agent-visible engine and `test_utils.py` frozen for Phase 18; oracle workspace's `engine/` may diverge with mechanic-specific extensions (miracle, casualty, paradigm primitives); audited tests use only canonical-engine APIs |
| `ADR-011` | Three-Tier Benchmark Locking — Beta/Benchmarking/Released lock scopes; forward-only non-reversible transitions; CI enforces base-branch tier (config.json never a locked path) |

## Harness Structure

```javascript
silverquillm/
  cli.py              # arg parsing + docker run + harvest
  card_loader.py      # card spec loading
  evaluator.py        # post-harvest test runner (3 dimensions)
  results.py          # run_summary.json generation
  results_repo.py     # private results repo: run-record schema + writer, leaderboard_valid rule, derived index (#39 §3)
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
