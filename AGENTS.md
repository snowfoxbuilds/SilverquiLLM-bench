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
- Tests: pytest with `test_utils` helpers, max 30 per card. Audited grader tests are host-side only, not run from the agent workspace.
- Three evaluation dimensions: target-set card correctness (SOS card correctness for SOS; HOB card correctness for the HOB generation), FDN card regression, engine regression
- Development phases: Phase 1 (engine port) → Phase 2 (container harness + audited tests) → Phase 3 (FDN completion + replay validation) → Phase 4 (SOS benchmark runs + leaderboard)

## Domain Language

See [CONTEXT.md](CONTEXT.md) for the project's domain glossary.

All specs, code, and agent instructions use these terms exactly.

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
| `DECISION-MODEL.md` | V2 engine Player Query / Player Decision protocol, Game Symbols/Refs, Intents, DeterministicPlayer (V2) — engine-level, pool-neutral |
| `BENCHMARK-CANDIDATES.md` | The bench-side candidate lifecycle (#39 §§4–5, #66): the curated `candidates/` tree and the promote gate (vendor-at-promote is strict), the file-backed batch queue and single-writer scheduler (`batches/`, `queue ls`, `top`), and the publish gate into `published/` (traceability = hard refusal, validity = warning; never commits) |
| `BENCH-CONTRACT.md` | The contract TheOzolith must publish for a Benchmark Candidate to equal a worker-type definition: build-context authentication, candidate-identity triple, bench-implementer run fidelity (vendored read-only from the-ozolith) |
| `KNOWN-ISSUES.md` | Known issues encountered during benchmark-runner development, with the fixes applied |

Each spec's own **Relevant ADRs** appendix links the architectural decisions behind it; there is no separate ADR index here.
