Status: SETTLED

Last updated: 2026-04-28

# Project Overview

MagicBench evaluates LLM coding ability by tasking models with implementing MTG cards as Python classes in a custom game engine.

## Context

Existing coding benchmarks (HumanEval, SWE-bench) don't capture the structured complexity of translating natural-language game rules into working code. MTG cards provide a natural difficulty gradient, verifiable correctness, and contamination resistance via new set releases.

## Design

### Why MTG?

- **Structured complexity** — Each card has precise rules text spanning trivial to extremely complex
- **Natural difficulty gradient** — A single set spans a wide complexity range
- **Verifiable correctness** — Deterministic testing against game rules + differential testing against XMage
- **Contamination resistance** — New sets release every few months; unreleased cards won't appear in training data
### Scope (v1)

| Parameter | Value |
| --- | --- |
| Language | Python |
| Engine | Python port of XMage (Java, GPL-2.0) |
| Base set | MTG Foundations (~260 cards, ported from XMage) |
| Target set | Secrets of Strixhaven (SOS, released 2026-04-24) |
| Agentic tool | OpenCode (permission controls for contamination) |
| Card scope | Full set (all card types) |
| Context limit | 200K tokens per agent session |
| Test iteration | Up to 3 rounds of test-informed code updates |

### Development Phases

**Phase 1 — Engine & Base Set** (COMPLETE)

Port XMage rules engine to Python. Implement MTG Foundations as the base set for engine validation and agent reference examples.

**Phase 2 — Benchmark Harness & Prototype**

Build benchmark runner harness, test utilities, rules lookup skill, and agent prompts. Prototype with ~5 Strixhaven cards to validate the full pipeline end-to-end.

**Phase 3 — Full Benchmark Run**

Port remaining Foundations cards as needed, catalog full Strixhaven set, run all agents across all cards, human audit, final scoring.

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
- **OpenCode as agentic tool**: Permission system enables contamination controls (deny web, restrict files). [SETTLED]
- **New set + no web for contamination**: Simple and effective for v1; avoids complex sandboxing. [SETTLED]
- **Full set scope**: Captures full difficulty distribution; enables per-complexity-tier analysis. [SETTLED]
- **Three scoring categories**: Blind implementation, implementation with tests, and test quality scored independently. [SETTLED]
