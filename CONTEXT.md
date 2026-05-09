# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs

use these terms exactly. Updated during grilling sessions.

## Terms

**Agent Adapter**

Pluggable interface (`AgentAdapter` base class) that translates the runner's prompts and workspace into a specific coding agent tool's native format. Each adapter enforces contamination controls for its tool.

*Avoid*: "agent tool" (ambiguous — could mean the adapter or the underlying tool itself)

**Audited Eval**

Third evaluation layer: all agents' implementations tested against human-curated gold-standard tests. The authoritative measure of correctness.

*Avoid*: "gold eval", "human eval"

**Base Set**

MTG Foundations limited format card pool (FDN 001–291 + SPG 074–083 Special Guests). Serves as engine validation, agent reference examples, and regression suite. Ported from XMage Java source. Engine validated via Replay Validation against 17lands GRE JSON data.

*Avoid*: "foundation cards" (use "Foundations cards" or "base set")

**Blind Implementation**

Step 1 of the benchmark: agent implements a card from its spec alone, with no tests or feedback. Saved as `blind_impl.py`.

*Avoid*: "first pass", "initial implementation"

**Card Spec**

JSON file (`card_spec.json`) containing a card's name, mana cost, type line, and oracle text. The only card-specific input provided to the agent.

*Avoid*: "card data", "card definition"

**Complexity Tier**

Classification of card difficulty: trivial (1×), simple (2×), medium (3×), complex (4×), expert (5×). Assigned via automated heuristics. Used for weighted scoring. Canonical key name in code and JSON is `complexity_tier` (not `tier`).

*Avoid*: "difficulty level", "tier" (as a standalone key name)

**Contamination**

When an LLM has seen target card implementations in its training data, invalidating the benchmark. Controlled via new set selection, no web access, and clean workspaces.

*Avoid*: "data leakage" (too generic)

**Cross-Eval**

Second evaluation layer: each agent's code tested against every other agent's tests, producing an N×N matrix. Reveals implementation quality and test quality simultaneously.

*Avoid*: "cross-validation" (overloaded ML term)

**DeterministicPlayer**

Test player with scripted actions for reproducible game state setup. All benchmark tests use this — no AI decision-making in v1.

*Avoid*: "test player", "mock player"

**Expanded Pool**

Cards from non-Foundations sets added to give agents reference examples for mechanics absent from Foundations (e.g., Ward, Magecraft for Strixhaven). Curated per target set.

*Avoid*: "extra cards", "supplemental cards"

**Pipeline Validation Run**

A benchmark run whose purpose is to validate that the orchestration pipeline works end-to-end (adapter integration, workspace setup, postmortem logging, regression checks, scoring). Not intended to produce meaningful scores — audited tests are not required. Precedes scored benchmark runs.

*Avoid*: "test run" (ambiguous), "dry run" (has a different meaning — `--dry-run` flag)

**Postmortem Log**

Structured JSONL file (`postmortem.jsonl`) capturing agent output, file diffs, test results, and reasoning traces per round per card. Primary source for debugging.

*Avoid*: "debug log", "session log"

**Replay Validation**

Engine correctness check that replays 17lands GRE (Game Rules Engine) state streams through the Python engine and verifies full game state at every GRE message boundary. Data source: 17lands pre-parsed GRE JSON — clean JSON files containing `GameStateType_Full` and `GameStateType_Diff` messages with object-level fidelity (zones, gameObjects by `grpId`/`instanceId`, life totals, annotations). Execution model: **observer mode** with state-diff comparison — seat 1 (17lands user) fully validated, seat 2 (opponent) actions oracle-injected from public game objects. Single parser, single format. See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) and [ADR-003](https://www.notion.so/37a8b903f91b4309a15b91d149a90f7c).

*Avoid*: "differential testing" (deprecated XMage approach), "checkpoint validation" (we do full state comparison, not just EOT checkpoints), "aggregate CSV" (that's a different 17lands dataset)

**Self-Eval**

First evaluation layer: each agent's code tested against its own tests. Unreliable alone (agents write easy tests) but useful as a baseline.

*Avoid*: "self-test"

**Setup Questions**

Structured JSON file (`setup_questions.json`) agents emit to flag workspace issues (missing files, engine gaps, ambiguous specs) instead of silently failing.

*Avoid*: "error report"

**Target Set**

The new MTG set whose cards agents must implement. For v1: Secrets of Strixhaven (set code SOS, released 2026-04-24). Chosen for contamination resistance.

*Avoid*: "benchmark set" (ambiguous with base set)

**Test-Informed Implementation**

Step 2 of the benchmark: agent writes tests and iterates on both tests and code, up to 3 rounds. Saved as `tested_impl.py` + `tests.py`.

*Avoid*: "test-driven implementation" (not TDD — agent writes code first)

**Persistent Engine**

The shared, writable copy of `engine/` that carries forward across all cards within a single benchmark run. Each run starts from the base engine; the agent's modifications accumulate as cards are processed sequentially. After each card, all previous cards' tests are re-run as a regression check.

*Avoid*: "shared engine" (use "persistent engine" or "run engine")

**Regression Check**

Automated re-run of all previously-completed cards' tests after each new card finishes. Catches engine modifications that break earlier cards. Regression failures are recorded per card and penalized in Category 4 scoring.

*Avoid*: "regression test" (too generic — this specifically means cross-card engine regression within a run)

**Engine Extension**

Modification or addition to `engine/` files by the agent during a benchmark run. Expected when a card requires a mechanic not yet supported. Good extensions are generic (reusable by future cards); bad extensions are card-specific hacks that break other cards.

*Avoid*: "engine modification" (neutral — use "engine extension" to imply additive/constructive intent)

**Workspace**

Clean temp directory created per card containing card-specific files (card_spec, template) plus a writable reference to the run's persistent engine. Fresh per card, but engine state carries forward.

*Avoid*: "working directory", "sandbox"

## Relationships

- A Benchmark Run evaluates one model + one Agent Adapter against one Target Set.
- A Benchmark Run has one Persistent Engine that starts from the base engine and accumulates Engine Extensions across cards.
- Cards within a run are processed sequentially, sorted by Complexity Tier.
- A Target Set contains many Card Specs, each with one Complexity Tier.
- Each agent produces one Blind Implementation and one Test-Informed Implementation per Card Spec.
- Each card may produce Engine Extensions that persist to subsequent cards' workspaces.
- After each card, a Regression Check re-runs all previous cards' tests against the current Persistent Engine.
- Cross-Eval tests every agent's implementations against every other agent's tests (N×N).
- The Base Set and Expanded Pool together form the reference codebase agents can browse.
- A Workspace is created per Card Spec within a run, with a writable reference to the Persistent Engine.
- The Base Set (FDN 001–291 + SPG 074–083) is validated via Replay Validation against 17lands GRE JSON data before scored benchmark runs.
- A Pipeline Validation Run precedes scored benchmark runs to verify the orchestration pipeline.
