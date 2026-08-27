Status: SETTLED

Last updated: 2026-05-30

# Project Overview

SilverquiLLM-bench evaluates LLM coding ability by tasking models with implementing MTG cards as Python classes in a custom game engine.

## Context

Existing coding benchmarks (HumanEval, SWE-bench) don't capture the structured complexity of translating natural-language game rules into working code. MTG cards provide a natural difficulty gradient, verifiable correctness, and contamination resistance via new set releases.

## Design

### Why MTG?

- **Structured complexity** — Each card has precise rules text spanning trivial to extremely complex
- **Natural difficulty gradient** — A single set spans a wide complexity range
- **Verifiable correctness** — Deterministic testing against game rules + Replay Validation against 17lands MTGA data
- **Contamination resistance** — New sets release every few months; unreleased cards won't appear in training data
### Scope (v1)

| Parameter | Value |
| --- | --- |
| Language | Python |
| Engine | Python port of XMage (Java, MIT) |
| Base set | MTG Foundations limited pool (FDN 001–291, ported from XMage) |
| Target set | Secrets of Strixhaven (SOS, released 2026-04-24) |
| Agentic tool | Docker container images: Pi (default), OpenCode, Claude Code, Aider (containerized black-box agents) |
| Card scope | Full set (all card types) |

### Development Phases

**Phase 1 — Engine & Base Set** (COMPLETE)

Ported XMage rules engine to Python. Implemented ~65 Foundations cards (basic lands, keyword creatures, simple spells, enchantments, planeswalkers, modal spells). Core engine systems complete.

**Phase 2 — Benchmark Harness & Prototype** (COMPLETE)

Built benchmark runner harness, test utilities, agent prompts, CLI scaffold, scoring system. Prototyped with SOS cards to validate pipeline. Wired CLI commands, contamination controls, and integration tests.

**Phase 3 — Base Set Completion & Pipeline Validation** (COMPLETE)

Implement all FDN cards 001–291 (limited format pool). Validate engine via Replay Validation against 17lands MTGA data. Run Pipeline Validation Runs to verify end-to-end orchestration.

FDN Replay Validation is **closed** (grilling 2026-08-27): observer mode fully clean (271/271, rate 0.0); the simulate-mode residue (5,222 divergences after Phase O) is 100% machine-attributed to documented limitation families (floor 564) and is accepted — none of it is engine-attributable. No further burn-down phases; a final parity report is the closing artifact ([`benchmarks/hob-medium/FDN-REPLAY-PARITY.md`](../../benchmarks/hob-medium/FDN-REPLAY-PARITY.md)). Cadence work reopens only if a future benchmark surfaces an actual engine bug in that area.

**Phase 4 — Scored Benchmark Runs** (CURRENT)

Curate audited gold-standard tests for SOS cards. Run all agents across full SOS set. Cross-eval consolidation. Produce scored leaderboards.

### Evaluation Architecture

Evaluation runs human-curated **audited tests** against every agent's implementation. There is no self-eval or N×N cross-eval — the current paradigm is audited tests plus cherry-picking (harvesting validated results and promoting strong cases into the audited suite). Three audited dimensions:

1. **SOS Card Correctness** — audited SOS tests vs. each agent's `card_impl.py`
2. **FDN Card Regression** — audited FDN tests vs. the agent's engine
3. **Engine Regression** — core engine tests vs. the agent's engine
The audited SOS suite is continuously improved by cherry-picking — see [AUDITED-TEST-IMPROVEMENT-WORKFLOW.md](https://app.notion.com/p/b99a10aff98e4794856ce259e4916163) and [AUDITED-TEST-SUITE.md](https://app.notion.com/p/a50ff4a1782e4badbc4419b6cbaface9).

### Related Work

- **mage-bench** — XMage + MCP bridge for LLMs playing MTG (not implementing cards)
- **ProxyWar** (ICSE 2026) — LLM game agent implementation via proxy patterns
- **PlayCoder** — LLM code generation for general game mechanics
## Decisions

- **Python over Java**: Most common LLM coding language; broadest model support. [SETTLED]
- **XMage port over custom engine**: Preserves battle-tested rules logic; Python is more LLM-friendly. [SETTLED]
- **MTG Foundations as base set**: Classic reprints covering all card types; gives agents working examples. [SETTLED]
- **Secrets of Strixhaven as target**: Released 2026-04-24 (set code SOS); too new to appear in training data. [SETTLED]
- **Harness-first development**: Build runner prototype before porting remaining Foundations cards; validate pipeline early with real Strixhaven cards. [SETTLED]
- **Multi-agent support**: Docker container images per agent. Each agent ships as a self-contained image with its own entrypoint. Contamination controlled structurally via container isolation. [UPDATED]
- **New set + no web for contamination**: Simple and effective for v1; avoids complex sandboxing. [SETTLED]
- **Full set scope**: Captures full difficulty distribution; enables per-complexity-tier analysis. [SETTLED]
- **Audited-only evaluation**: SOS card correctness (audited tests vs. agent impls), FDN card regression (audited FDN tests vs. agent's engine), engine regression (core engine tests vs. agent's engine). Self-eval and N×N cross-eval were dropped in favor of audited tests refined by cherry-picking; automated cross-eval / test-quality scoring remains a possible v2 Test Harvester. [UPDATED]
