# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs

use these terms exactly. Updated during grilling sessions.

## Terms

**Agent Container**

Docker image packaging a single coding agent with its CLI, entrypoint, mode (blind/tested), strategy, model selection, and prompt — the full benchmark configuration. The runner launches it with mounted volumes and API key env vars. The runner has zero knowledge of agent internals. Image name encodes the variant (e.g. `silverquillm-opencode-tested:latest`).

*Avoid*: "agent adapter" (deprecated), "agent tool" (ambiguous)

**Audited Eval**

The only evaluation method in v1: audited tests run against agent output post-run. Three dimensions: SOS card correctness, FDN card regression, engine regression. Tests are LLM-drafted, then failure-reviewed by a human. The authoritative measure of correctness.

*Avoid*: "gold eval", "human eval"

**Base Set**

The FDN Draft Set: MTG Foundations limited format card pool (FDN 001–291 + SPG 074–083 Special Guests). Serves as engine validation, agent reference examples, and regression suite. Ported from XMage Java source. Engine validated via Replay Validation against 17lands GRE JSON data.

*Avoid*: "foundation cards" (use "Foundations cards" or "base set")

**Blind Mode**

Benchmark mode (`MODE=blind`) where the prompt does not instruct the agent to write or run tests. The agent still has access to pytest — the distinction is prompt-only for v1. Produces `card_impl.py` per card. Compare against Tested Mode via separate runs.

*Avoid*: "blind implementation" as a noun (deprecated — was `blind_impl.py`)

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

**Cross-Eval** *(deferred — v2)*

Future evaluation layer: each agent's code tested against every other agent's tests, producing an N×N matrix. Requires a test harvester to collect and validate agent-written tests. Not part of v1 scoring.

*Avoid*: "cross-validation" (overloaded ML term)

**Draft Set**

All cards contained in draft booster packs for a given MTG release. A Draft Set may span multiple Scryfall set codes. The SOS Draft Set = SOS base (cn ≤271) + SOA Mystical Archives (cn 1–65) + SPG Special Guests (cn 149–158). The FDN Draft Set = FDN 001–291 + SPG 074–083. Draft Set defines the card pool for Replay Validation because 17lands replays are from draft games.

*Avoid*: "target set" (deprecated), "set" alone (ambiguous — could mean a single Scryfall set code)

**DeterministicPlayer**

Test player with scripted actions for reproducible game state setup. All benchmark tests use this — no AI decision-making in v1.

*Avoid*: "test player", "mock player"

**Pipeline Validation Run**

A benchmark run whose purpose is to validate that the orchestration pipeline works end-to-end (workspace staging, container launch, result harvesting, evaluation). Not intended to produce meaningful scores — audited tests are not required. Precedes scored benchmark runs.

*Avoid*: "test run" (ambiguous), "dry run" (has a different meaning — `--dry-run` flag)

**Progress Log**

JSONL file (`progress.jsonl`) written by the agent or entrypoint to `/output/progress.jsonl` inside the container. Records per-card status updates (started, tests_passing, completed). Mounted volume allows the runner to tail it in real time. Replaces the former Postmortem Log.

*Avoid*: "postmortem log" (deprecated — was per-round per-card structured JSONL)

**Replay Validation**

Engine correctness check that replays 17lands GRE (Game Rules Engine) state streams through the Python engine and verifies full game state at every GRE message boundary. Data source: 17lands pre-parsed GRE JSON — clean JSON files containing `GameStateType_Full` and `GameStateType_Diff` messages with object-level fidelity (zones, gameObjects by `grpId`/`instanceId`, life totals, annotations). Execution model: **observer mode** with state-diff comparison — seat 1 (17lands user) fully validated, seat 2 (opponent) actions oracle-injected from public game objects. Single parser, single format. See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) and [ADR-003](https://www.notion.so/37a8b903f91b4309a15b91d149a90f7c).

*Avoid*: "differential testing" (deprecated XMage approach), "checkpoint validation" (we do full state comparison, not just EOT checkpoints), "aggregate CSV" (that's a different 17lands dataset)

**Self-Eval** *(deferred — v2)*

Future evaluation layer: each agent's code tested against its own tests. Requires test harvester. Not part of v1 scoring.

*Avoid*: "self-test"

**Tested Mode**

Benchmark mode (`MODE=tested`) where the prompt instructs the agent to write tests and iterate. The agent self-manages iteration — no round limits enforced by the runner. Produces `card_impl.py` + `tests.py` per card. Compare against Blind Mode via separate runs.

*Avoid*: "test-informed implementation" (deprecated — was `tested_impl.py`)

**Writable Engine**

The agent's copy of `engine/` at `/workspace/engine_work/` inside the container. Copied from the read-only `/workspace/engine/` by the entrypoint before the agent starts. The agent modifies it freely throughout the run. After the run, the runner diffs it against the original to produce `engine_diff.patch`.

*Avoid*: "persistent engine" (deprecated — implied per-card sequential accumulation), "shared engine"

**FDN Card Regression**

Post-run evaluation dimension: FDN audited tests (`tests/audited/fdn/`) run against pre-filled FDN `card_impl.py` files using the agent's final Writable Engine. Detects whether engine extensions broke existing card behavior.

*Avoid*: "regression check" (deprecated — was per-card sequential re-run)

**Engine Regression**

Post-run evaluation dimension: core engine tests (`tests/engine/`) run against the agent's final Writable Engine. Detects whether engine extensions broke fundamental game mechanics (mana, stack, combat, state-based actions, etc.). Separate from FDN Card Regression — an agent could pass all FDN card tests but fail engine tests if card-level workarounds corrupt internal state.

*Avoid*: "engine test" alone (ambiguous — specify "engine regression tests")

**Engine Extension**

Modification or addition to `engine/` files by the agent during a benchmark run. Expected when a card requires a mechanic not yet supported. Good extensions are generic (reusable by future cards); bad extensions are card-specific hacks that break other cards.

*Avoid*: "engine modification" (neutral — use "engine extension" to imply additive/constructive intent)

**Workspace**

The staged directory mounted into the agent container at `/workspace/`. Contains all cards (FDN examples + SOS targets), the engine, rulebook, reference docs, and a single prompt. Created once per run by the runner's `stage_workspace()`. The agent has read-write access to the entire workspace.

*Avoid*: "working directory", "sandbox", "per-card workspace" (deprecated — workspace is per-run)

## Relationships

- A Benchmark Run evaluates one Agent Container (one agent + one model) against one Draft Set.
- A Benchmark Run launches one container session. The agent receives the full workload (all SOS cards) in a single Workspace.
- FDN cards are in-context examples (filled implementations, no tests). SOS cards are benchmark targets (empty templates).
- Each agent produces `card_impl.py` per SOS card. In Tested Mode, also `tests.py` per card.
- The agent has a Writable Engine (`engine_work/`) and may extend it freely throughout the run.
- All evaluation is post-run. After the container exits, the evaluator runs tests against harvested implementations and the final engine state.
- FDN Card Regression: evaluator runs `tests/audited/fdn/` against pre-filled FDN card impls + agent's final Writable Engine. Detects broken card behavior.
- Engine Regression: evaluator runs `tests/engine/` against agent's final Writable Engine. Detects broken rules mechanics.
- Cross-Eval and Self-Eval deferred to v2 (requires test harvester).
- The Base Set forms the reference codebase agents can browse. No Expanded Pool — agents implement new mechanics from scratch.
- A Draft Set may span multiple Scryfall set codes (e.g., SOS + SOA + SPG).
- Draft Set defines the card pool for Replay Validation (17lands replays are draft games).
- All card tests follow a uniform structure: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. FDN and SOS tests share this structure.
- The Base Set (FDN 001–291 + SPG 074–083) is validated via Replay Validation against 17lands GRE JSON data before scored benchmark runs.
- A Pipeline Validation Run precedes scored benchmark runs to verify the orchestration pipeline.
- Filesystem checks (does the file exist, does it differ from the template?) are the source of truth for agent output. Exit codes, stdout, and thinking traces are diagnostics only.
- `run_summary.json` is automatically generated after evaluation by aggregating per-card `result.json` files. The aggregator is a pure, idempotent function.
- The runner does NOT orchestrate test iteration — the agent self-manages. The runner stages, launches, harvests, evaluates.
- On container timeout, the runner harvests partial results. Completed cards are evaluated normally; unfinished cards scored as zero.
- Two benchmark modes: **Blind** (prompt omits test instructions) and **Tested** (prompt includes test instructions). Both produce `card_impl.py`. Distinction is prompt-only for v1. Compare modes via separate runs.
- Audited tests are evaluation-only artifacts — never in the agent's workspace, never in results directories. Contamination control.
