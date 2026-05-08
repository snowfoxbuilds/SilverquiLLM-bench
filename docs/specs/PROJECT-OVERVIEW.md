Status: SETTLED

Last updated: 2026-04-28

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
| Agentic tool | Pluggable adapters: OpenCode, Claude Code, Aider, Pi (each enforces contamination controls) |
| Card scope | Full set (all card types) |
| Context limit | 200K tokens per agent session |
| Test iteration | Up to 3 rounds of test-informed code updates |

### Development Phases

**Phase 1 — Engine & Base Set** (COMPLETE)

Ported XMage rules engine to Python. Implemented ~65 Foundations cards (basic lands, keyword creatures, simple spells, enchantments, planeswalkers, modal spells). Core engine systems complete.

**Phase 2 — Benchmark Harness & Prototype** (COMPLETE)

Built benchmark runner harness, test utilities, agent prompts, CLI scaffold, scoring system. Prototyped with SOS cards to validate pipeline. Wired CLI commands, contamination controls, and integration tests.

**Phase 3 — Multi-Agent Adapters & Persistent Engine** (COMPLETE)

Renamed package to `silverquillm`. Introduced pluggable adapter abstraction (OpenCode, Claude Code, Aider, Pi). Added postmortem logging, setup questions, persistent engine per run, regression test runner, engine diff capture, and Category 4 scoring.

**Phase 4 — Base Set Completion & Pipeline Validation** (CURRENT)

Implement all FDN cards 001–291 (limited format pool). Validate engine via Replay Validation against 17lands MTGA data. Run Pipeline Validation Runs to verify end-to-end orchestration.

**Phase 5 — Scored Benchmark Runs**

Curate audited gold-standard tests for SOS cards. Run all agents across full SOS set. Cross-eval consolidation. Produce scored leaderboards.

### Evaluation Architecture

Three-layer evaluation:

1. **Self-eval** — Agent's code against its own tests
2. **Cross-eval** — Agent's code against every other agent's tests (N×N matrix)
3. **Audited eval** — All agents' code against human-curated gold-standard tests
### Related Work

- **mage-bench** — XMage + MCP bridge for LLMs playing MTG (not implementing cards)
- **ProxyWar** (ICSE 2026) — LLM game agent implementation via proxy patterns
- **PlayCoder** — LLM code generation for general game mechanics
## Decisions

- **Python over Java**: Most common LLM coding language; broadest model support. [SETTLED]
- **XMage port over custom engine**: Preserves battle-tested rules logic; Python is more LLM-friendly. [SETTLED]
- **MTG Foundations as base set**: Classic reprints covering all card types; gives agents working examples. [SETTLED]
- **Secrets of Strixhaven as target**: Released 2026-04-24 (set code SOS); new mechanics (Prepared, Converge, Miracle, Opus) won't be in training data. [SETTLED]
- **Harness-first development**: Build runner prototype before porting remaining Foundations cards; validate pipeline early with real Strixhaven cards. [SETTLED]
- **Multi-agent support**: Pluggable adapter pattern supports OpenCode, Claude Code, Aider, Pi. Each adapter enforces contamination controls. [UPDATED]
- **New set + no web for contamination**: Simple and effective for v1; avoids complex sandboxing. [SETTLED]
- **Full set scope**: Captures full difficulty distribution; enables per-complexity-tier analysis. [SETTLED]
- **Four scoring categories**: Blind implementation, implementation with tests, test quality, and engine extension quality scored independently. [UPDATED]
