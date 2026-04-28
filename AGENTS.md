# MagicBench

LLM benchmark that evaluates coding ability by tasking models with implementing Magic: The Gathering cards as Python classes in a custom game engine. Uses cards from the newest MTG set (not yet in training data) to minimize contamination.

## Conventions

- Language: Python 3.11+
- Engine: Python port of XMage (Java GPL-2.0)
- Base set: MTG Foundations (~260 cards ported from XMage)
- Target benchmark set: Secrets of Strixhaven (SOS, released 2026-04-24)
- Agentic tool: OpenCode
- License: GPL-2.0
- Card implementations: one class per card, subclassing `CardImpl`
- Tests: pytest with `test_utils` helpers, max 30 per card
- Three scoring categories: blind implementation, implementation with tests, test quality
- Development order: Phase 1 (engine) → Phase 2 (harness prototype with real SOS cards) → Phase 3 (full run)
## Specs

| File | Summary |
| --- | --- |
| `docs/specs/PROJECT-OVERVIEW.md` | Project purpose, scope, development phases, and key decisions |
| `docs/specs/GAME-ENGINE.md` | Python port of XMage rules engine, core systems, and game state API |
| `docs/specs/CARD-INTERFACE.md` | Card class hierarchy, hook methods, and supporting types |
| `docs/specs/TEST-SUITE.md` | Multi-phase evaluation architecture, cross-evaluation, and test audit |
| `docs/specs/BENCHMARK-RUNNER.md` | Orchestration harness, agent prompts, contamination controls |
| `docs/specs/SCORING.md` | Three scoring categories, metrics, and leaderboard format |
