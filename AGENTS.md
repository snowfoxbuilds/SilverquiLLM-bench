# SilverquiLLM-bench

LLM benchmark that evaluates coding ability by tasking models with implementing Magic: The Gathering cards as Python classes in a custom game engine. Uses cards from the newest MTG set (not yet in training data) to minimize contamination. Python package name: `silverquillm`.

## Conventions

- Language: Python ≥3.12
- Engine: Python port of XMage (Java, MIT)
- Base set: FDN Draft Set (301 cards: FDN 001–291 + SPG 074–083) — used as in-context examples
- Benchmark set: SOS Draft Set (271 cards: SOS 001–271, released 2026-04-24) — benchmark targets
- Agents: Karn-built images paired with v4 Construct Definitions, executed by SilverquiLLM's own benchmark host with no Ozolith dependency; candidate code is graded only in a network-less grader container
- License: MIT (matching XMage)
- Card implementations: one class per card, subclassing `CardImpl`
- Tests: pytest with `test_utils` helpers, max 30 per card. Audited grader tests are host-side only, not run from the agent workspace; staged Reference Tests are editable and never graded.
- Three evaluation dimensions: target-set card correctness (SOS card correctness for SOS; HOB card correctness for the HOB generation), FDN card regression, engine regression; the two regression dimensions pool into a Combined Regression reported against a Baseline Score and a Known-Best Score
- Pull requests: CI (`.github/workflows/ci.yml`; tests on the self-hosted runner, label jobs GitHub-hosted) owns the `tests-passed` and `tests-failed` labels and comments on a failure; a push to the pull request removes both. Agents never add either label. Before pushing, an implementer runs only the tests its change touches; CI runs the full suite. Add `request-review` when a pull request is ready for review; a reviewer takes it once CI has added `tests-passed`.
- Review routing: every pull request carries exactly one `implementer:claude` or `implementer:codex` label naming the agent family that wrote it, added by its author on opening. The other family's reviewer takes it — `implementer:claude` goes to the Codex reviewer, `implementer:codex` to the Claude reviewer — and a pull request with neither label is never reviewed. A human merges.
- Pushing back: a reviewer's findings are advice, not orders, and its verdict is not the final word. An implementer that judges a finding wrong may push back, saying why in a reply on the pull request, and then adds `request-review` again; the human who merges decides.
- Karn integration purpose: collect run data, learn, and improve; retain failures and incomplete observations without a leaderboard eligibility gate
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
| `BENCHMARK-RUNNER.md` | The historical `--image` lineage (`silverquillm legacy`) and reusable workspace/harvesting reference; Karn v4 execution is in KARN-BENCHMARK-CONTRACT.md |
| `SCORING.md` | Three evaluation dimensions, complexity weighting, leaderboard format |
| `AGENT-CONTAINERS.md` | Docker black-box architecture, file-based contract, entrypoint design, isolation guarantees |
| `WORKSPACE-CONTRACT.md` | Workspace layout, card directory invariant, Run Manifest, writable engine, FDN/SOS structure |
| `RUN-ARTIFACTS-AND-TELEMETRY.md` | Existing artifact layouts, workspace snapshots and recovery; Karn v4 observations are governed by KARN-BENCHMARK-CONTRACT.md |
| `TESTING-CONVENTIONS.md` | Test naming, fixtures, assertions, and conventions for audited tests |
| `17LANDS-REPLAY-SCHEMA.md` | GRE JSON replay format for engine correctness validation |
| `AUDITED-TEST-IMPROVEMENT-WORKFLOW.md` | Harvest script + combined investigation/discovery skill (manual v1 Test Harvester); harvest format, fault-attribution triage, promotion bar, cadence, tier gating |
| `HOB-BENCHMARKS.md` | The three HOB-generation benchmarks (hob-easy/medium/hard): picked pools (23/5/5, selective subsets of the HOB set), run shape, engine freeze + tests-as-envelope, instruction docs, candidate contract |
| `FRA-HARD-BENCHMARK.md` | The ten-card mixed FRA/HOB hard benchmark: selected pool, qualified card identities, independent oracle, and hidden evaluation |
| `KNOWN-BEST-ENGINE.md` | The Known-Best Workspace and Engine, per-benchmark Known Defects, the baseline reference grade, and how newly found defects and wrong Audited Tests are fixed |
| `DECISION-MODEL.md` | V2 engine Player Query / Player Decision protocol, Game Symbols/Refs, Intents, DeterministicPlayer (V2) — engine-level, pool-neutral |
| `BENCHMARK-CANDIDATES.md` | Retired: the removed Candidate Bundle promotion, batch, and publication pipeline, and what of it remains readable |
| `BENCH-CONTRACT.md` | Historical Candidate Bundle and production Implementer Run contract (vendored read-only from the-ozolith); reference for legacy candidates |
| `KARN-BENCHMARK-CONTRACT.md` | The bench-owned Karn v4 consumer contract: explicit builds, independent execution, grading isolation, implementation-only tasks, and subscription authentication |
| `KNOWN-ISSUES.md` | Known issues encountered during benchmark-runner development, with the fixes applied |

Each spec's own **Relevant ADRs** appendix links the architectural decisions behind it; there is no separate ADR index here.
