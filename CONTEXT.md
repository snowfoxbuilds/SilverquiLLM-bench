# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs

use these terms exactly. Updated during grilling sessions.

## Terms

**Agent Adapter**

Pluggable interface (`AgentAdapter` base class) that translates the runner's prompts and workspace into a specific coding agent tool's native format. Each adapter enforces contamination controls for its tool.

*Avoid*: "agent tool" (ambiguous — could mean the adapter or the underlying tool itself)

**Audited Eval**

Third evaluation layer: all agents' implementations tested against gold-standard tests. Tests are LLM-drafted, then failure-reviewed by a human — failures during benchmark runs are reviewed and corrected by hand; passing tests are accepted as-is. The authoritative measure of correctness.

*Avoid*: "gold eval", "human eval"

**Base Set**

The FDN Draft Set: MTG Foundations limited format card pool (FDN 001–291 + SPG 074–083 Special Guests). Serves as engine validation, agent reference examples, and regression suite. Ported from XMage Java source. Engine validated via Replay Validation against 17lands GRE JSON data.

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

**Card Pool**

Synonym for Draft Set when referring to the set of cards included in a benchmark. The SOS Card Pool = SOS Draft Set.

*Avoid*: "target set" (deprecated — was ambiguous about whether it meant a single Scryfall set code or the full draft pool)

**Contamination**

When an LLM has seen target card implementations in its training data, invalidating the benchmark. Controlled via new set selection, no web access, and clean workspaces.

*Avoid*: "data leakage" (too generic)

**Cross-Eval**

Second evaluation layer: each agent's code tested against every other agent's tests, producing an N×N matrix. Reveals implementation quality and test quality simultaneously.

*Avoid*: "cross-validation" (overloaded ML term)

**Draft Set**

All cards contained in draft booster packs for a given MTG release. A Draft Set may span multiple Scryfall set codes. The SOS Draft Set = SOS base (cn ≤271) + SOA Mystical Archives (cn 1–65) + SPG Special Guests (cn 149–158). The FDN Draft Set = FDN 001–291 + SPG 074–083. Draft Set defines the card pool for Replay Validation because 17lands replays are from draft games.

*Avoid*: "target set" (deprecated), "set" alone (ambiguous — could mean a single Scryfall set code)

**DeterministicPlayer**

Test player with scripted actions for reproducible game state setup. All benchmark tests use this — no AI decision-making in v1.

*Avoid*: "test player", "mock player"

**Expanded Pool** *(deprecated — dropped)*

Originally planned: cards from non-Foundations sets added as reference examples for mechanics absent from Foundations. Dropped — agents implement new mechanics from scratch using oracle text + comprehensive rules. Better benchmark signal.

*Avoid*: using this term — it no longer applies

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

**Target Set** *(deprecated — use Draft Set)*

Formerly: the new MTG set whose cards agents must implement. Replaced by Draft Set because the benchmark card pool spans multiple Scryfall set codes (SOS + SOA + SPG), not a single set. For v1 the target Draft Set is SOS (released 2026-04-24).

*Avoid*: using this term in new code or specs — use "Draft Set" or "Card Pool" instead

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
- The Base Set forms the reference codebase agents can browse. No Expanded Pool — agents implement new mechanics from scratch.
- A Draft Set may span multiple Scryfall set codes (e.g., SOS + SOA + SPG).
- Draft Set defines the card pool for Replay Validation (17lands replays are draft games).
- Audited tests follow a uniform per-card structure: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. Reusable across any set.
- A Workspace is created per Card Spec within a run, with a writable reference to the Persistent Engine.
- The Base Set (FDN 001–291 + SPG 074–083) is validated via Replay Validation against 17lands GRE JSON data before scored benchmark runs.
- A Pipeline Validation Run precedes scored benchmark runs to verify the orchestration pipeline.
