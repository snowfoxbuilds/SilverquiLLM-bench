# SilverquiLLM-bench

LLM benchmark that evaluates coding ability by tasking models with implementing Magic: The Gathering cards as Python classes in a custom game engine. Uses cards from the newest MTG set (not yet in training data) to minimize contamination. Python package name: `silverquillm`.

## Conventions

- Language: Python ≥3.12 (per KEY_DECISIONS #2)
- Engine: Python port of XMage (Java, MIT)
- Base set: FDN Draft Set (301 cards: FDN 001–291 + SPG 074–083)
- Benchmark Draft Set: SOS Draft Set (346 cards: SOS ≤271 + SOA 1–65 + SPG 149–158, released 2026-04-24)
- Agentic tools: Pluggable adapters (OpenCode, Claude Code, Aider, Pi)
- License: MIT (matching XMage)
- Card implementations: one class per card, subclassing `CardImpl`
- Tests: pytest with `test_utils` helpers, max 30 per card
- Four scoring categories: blind implementation, implementation with tests, test quality, engine extension quality
- Development order: Phase 1 (engine) → Phase 2 (harness prototype) → Phase 3 (adapters, persistent engine) → Phase 4 (base set completion) → Phase 5 (replay validation pipeline) → Phase 6 (SOS Draft Set completion & audited test suites)
## Domain Language

See [CONTEXT.md](http://context.md/) for the project's domain glossary.

All specs, code, and agent instructions use these terms exactly.

## Specs

| File | Summary |
| --- | --- |
| `docs/specs/PROJECT-OVERVIEW.md` | Project purpose, scope, development phases, and key decisions |
| `docs/specs/GAME-ENGINE.md` | Python port of XMage rules engine, core systems, and game state API |
| `docs/specs/CARD-INTERFACE.md` | Card class hierarchy, hook methods, and supporting types |
| `docs/specs/TEST-SUITE.md` | Multi-phase evaluation architecture, cross-evaluation, and test audit |
| `docs/specs/BENCHMARK-RUNNER.md` | Orchestration harness, agent prompts, contamination controls |
| `docs/specs/SCORING.md` | Three scoring categories, metrics, and leaderboard format |
| `docs/specs/17LANDS-REPLAY-SCHEMA.md` | GRE JSON replay format: events, gameStateMessage, zones, gameObjects, annotations, parsing strategy |

## ADRs

Architectural decisions are documented under the ADRs page:

| ADR | Summary |
| --- | --- |
| `docs/adr/ADR-001` | SQLite-based card data over Scryfall API |
| `docs/adr/ADR-002` | Per-card unit tests over differential testing during porting |
| `docs/adr/ADR-003` | Replay Validation over differential testing — 17lands GRE JSON, observer mode, full state-diff comparison |
