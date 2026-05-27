# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs

use these terms exactly. Updated during grilling sessions.

## Terms

**Agent Container**

Docker image packaging a single coding agent with its CLI, entrypoint, mode (blind/tested), strategy, model selection, and prompt — the full benchmark configuration. The runner launches it with mounted volumes and API key env vars. The runner has zero knowledge of agent internals. Image name encodes the variant (e.g. `silverquillm-pi-blind:latest`).

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

All cards contained in draft booster packs for a given MTG release. A Draft Set may span multiple Scryfall set codes. The SOS Draft Set = SOS base (cn 001–271). The FDN Draft Set = FDN 001–291 + SPG 074–083. Draft Set defines the card pool for Replay Validation because 17lands replays are from draft games.

*Avoid*: "target set" (deprecated), "set" alone (ambiguous — could mean a single Scryfall set code)

**DeterministicPlayer**

Test player with scripted actions for reproducible game state setup. All benchmark tests use this — no AI decision-making in v1.

*Avoid*: "test player", "mock player"

**Output Snapshot**

Periodic runner-captured copy of the Workspace during an Agent Container run, roughly once per minute. Stored as host-side Git commits outside the container. Used for progress telemetry and as a fallback recovery point if final Workspace state is corrupted by timeout cutoff or broken engine edits.

*Avoid*: "checkpoint" (overloaded with spec checkpoints), "progress log" (that's `progress.jsonl`)

**Pipeline Validation Run**

A benchmark run whose purpose is to validate that the orchestration pipeline works end-to-end (workspace staging, container launch, result harvesting, evaluation). Not intended to produce meaningful scores — audited tests are not required. Precedes scored benchmark runs.

*Avoid*: "test run" (ambiguous), "dry run" (has a different meaning — `--dry-run` flag)

**Replay Validation**

Engine correctness check that replays 17lands GRE (Game Rules Engine) state streams through the Python engine and verifies full game state at every GRE message boundary. Data source: 17lands pre-parsed GRE JSON — clean JSON files containing `GameStateType_Full` and `GameStateType_Diff` messages with object-level fidelity (zones, gameObjects by `grpId`/`instanceId`, life totals, annotations). Execution model: **observer mode** with state-diff comparison — seat 1 (17lands user) fully validated, seat 2 (opponent) actions oracle-injected from public game objects. Single parser, single format. See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) and [ADR-003](https://www.notion.so/37a8b903f91b4309a15b91d149a90f7c).

*Avoid*: "differential testing" (deprecated XMage approach), "checkpoint validation" (we do full state comparison, not just EOT checkpoints), "aggregate CSV" (that's a different 17lands dataset)

**Resume Chain**

Sequence of Benchmark Runs linked via `resumed_from`, where each run after the first stages from the prior run's `workspace_final/`. Each leg is an independent Benchmark Run with its own `run_name`, results directory, Hard Timeout, snapshots, and evaluation. The chain is an audit-trail concept; the runner does not aggregate results across legs. CLI: `silverquillm resume <prior-run-id>`. See ADR-008.

*Avoid*: "session" (deprecated — too vague; use Resume Chain + Resume Leg), "continuation run"

**Resume Leg**

A Benchmark Run with `resumed_from` set — any run in a Resume Chain other than the first. Resume Legs are independent Benchmark Runs in every other respect (own results dir, own snapshots, own evaluation, own `run_summary.json`). Leaderboard validity policy for Resume Legs is TBD — the existing `leaderboard_valid` field in `run_summary.json` is the eventual control surface; default for legs is unspecified until policy is formalized.

*Avoid*: "resumed session", "continuation run"

**Resume Preamble**

Extra lines the runner appends to the User Prompt when staging a Resume Leg. Always informs the agent (a) that this is a resume of `<prior-run-id>`, (b) that prior tests/implementations may already exist, and (c) that the workspace `.git` records prior commits. Conditional additional lines disclose (i) prior-run snapshot-fallback rollback when applicable, and (ii) image change when `--image` differs from the prior run's image. Image-agnostic — agents with no internal coordinator/cycle structure benefit equally.

*Avoid*: "resume notice", "resume header"

**Run Manifest**

Minimal runtime facts written by the runner to `/workspace/run_manifest.json` immediately before container launch. Contains only `timeout_seconds` and `deadline_utc`; it is advisory to the Agent Container and does not configure agent behavior.

*Avoid*: "config.json" (implies agent configuration), "agent config"

**Self-Eval** *(deferred — v2)*

Future evaluation layer: each agent's code tested against its own tests. Requires test harvester. Not part of v1 scoring.

*Avoid*: "self-test"

**Tested Mode**

Benchmark mode (`MODE=tested`) where the prompt instructs the agent to write tests and iterate. The agent self-manages iteration — no round limits enforced by the runner. Produces `card_impl.py` + `tests.py` per card. Compare against Blind Mode via separate runs.

*Avoid*: "test-informed implementation" (deprecated — was `tested_impl.py`)

**Writable Engine**

The engine source at `/workspace/engine/` inside the container. The agent modifies it in place throughout the run. The baseline engine remains on the host side, outside the container; after the run, the runner diffs the final or fallback Workspace engine against the host baseline to produce `engine_diff.patch`.

*Avoid*: "persistent engine" (deprecated — implied per-card sequential accumulation), "shared engine"

**FDN Reference Tests**

Illustrative pytest files colocated with FDN reference implementations at `cards/fdn/{collector_number}/tests.py`. Agent-visible inside the Workspace. Demonstrate the testing pattern (DeterministicPlayer scripts, expected-state asserts) so agents can model `cards/sos/{card_id}/tests.py` after them in Tested Mode. Distinct from FDN Card Regression — these are learning material, not grading input. Modifying them does not affect score.

*Avoid*: "FDN tests" alone (ambiguous — specify Reference vs Card Regression), "FDN illustrative tests" (use "FDN Reference Tests")

**FDN Card Regression**

Post-run evaluation dimension: FDN audited tests (`tests/audited/fdn/`) run against pre-filled FDN `card_impl.py` files using the agent's final Writable Engine. Detects whether engine extensions broke existing card behavior. Host-side only; not staged into the Workspace. Distinct from FDN Reference Tests.

*Avoid*: "regression check" (deprecated — was per-card sequential re-run), "FDN tests" alone (ambiguous — specify Reference vs Card Regression)

**Engine Regression**

Post-run evaluation dimension: core engine tests (`tests/engine/`) run against the agent's final Writable Engine. Detects whether engine extensions broke fundamental game mechanics (mana, stack, combat, state-based actions, etc.). Separate from FDN Card Regression — an agent could pass all FDN card tests but fail engine tests if card-level workarounds corrupt internal state.

*Avoid*: "engine test" alone (ambiguous — specify "engine regression tests")

**Engine Extension**

Modification or addition to `engine/` files by the agent during a benchmark run. Expected when a card requires a mechanic not yet supported. Good extensions are generic (reusable by future cards); bad extensions are card-specific hacks that break other cards.

*Avoid*: "engine modification" (neutral — use "engine extension" to imply additive/constructive intent)

**Workspace**

The directory at `benchmarks/sos/workspace/` in the bench repo, copied wholesale to a per-run tmp path and mounted into the agent container at `/workspace/`. Contains the engine (canonical single copy, shared with bench tooling), all cards (FDN reference implementations + SOS Card Stubs), tests (`tests/conftest.py`, `tests/test_utils.py`, `tests/engine/`), agent-facing documentation (`AGENTS.md`, `PROJECT_MAP.md`, `rulebook.txt`), and supporting files (`pytest.ini`, `.gitignore`). Per-run files (`prompt.md`, `run_manifest.json`) are written into the copy at stage time, followed by an initial `git init && git commit` so the agent has clean version-control state. The resume staging variant (see Resume Chain) skips `git init` and preserves the prior run's `workspace_final/` `.git` history instead. The agent has read-write access to the entire workspace.

*Avoid*: "working directory", "sandbox", "per-card workspace" (deprecated — workspace is per-run), "staged from scratch" (deprecated — workspace is a pre-built directory copied wholesale)

**SOS Card Stub**

The starting-state `card_impl.py` for an SOS card: a `class CardName(CardImpl): pass` declaration with a TODO docstring. Pins class name, inheritance, and import path so audited tests can reliably import. Provides no behavior — `CardImpl` is no-op-by-default (all hooks return safe defaults), so stubs are runnable from day one and tests fail on missing behavior, not import/structure. The agent's task is to fill in the class body.

*Avoid*: "empty template" (technically inaccurate — stubs are non-empty), "skeleton card"

**Hard Timeout**

Overall wall-clock time limit for a benchmark run, enforced by the runner via monotonic clock check in the main poll loop. The runner writes `timeout_seconds` and `deadline_utc` to the Run Manifest before launch and stops the container when the deadline passes. CLI flag: `--timeout`.

*Avoid*: "container timeout" (ambiguous — could mean Docker's `--stop-timeout` grace period)

**Hang Timeout**

Secondary timeout that triggers when no monitored file activity (Docker pipe output, `/output/` files) occurs for a configurable period during a benchmark run. Catches catastrophic agent failures (process death, API outage, infinite loops) without false-positiving on long thinking pauses. CLI flag: `--hang-timeout`.

*Avoid*: "idle timeout" (implies workspace-only activity check)

**System Prompt**

Agent-optimization instructions baked into the Docker image's entrypoint. Controls how the agent executes (iteration strategy, mode-specific behavior, tool configuration). Not written by the runner. Contrast with User Prompt.

*Avoid*: "agent prompt" (ambiguous — could mean either prompt layer)

**User Prompt**

Task-specific instruction written by the runner to `/workspace/prompt.md` at staging time. Describes what the agent should implement (e.g., "Implement all SOS cards in `/workspace/cards/sos/`"). Adjusted for filtered runs to list only staged cards. Contrast with System Prompt.

*Avoid*: "task prompt", "workspace prompt"

**Ability Word**

Italicized flavor label printed on a card naming a triggered or static effect (e.g. Converge, Prepared, Opus, Paradigm, Landfall, Heroic). Has no inherent rules meaning — the actual rules text follows the label and produces the behavior. Tests target the behavior described by that text, never the label itself.

*Avoid*: "keyword" (Ability Words are not Keyword Abilities), "flag", "tag"

**Keyword Ability**

MTG rules construct the engine implements (e.g. Flying, Reach, Deathtouch, Affinity, Casualty, Cascade, the Miracle keyword). Cards with a Keyword Ability inherit its rules text by reference. Tests probe the behavior produced by the keyword, not just presence in a `keywords[]` list.

*Avoid*: "ability word" (distinct concept — see Ability Word)

**Test Oracle Impl**

Host-side `card_impl.py` inside the Test Oracle Workspace that encodes the correct mechanic for one audited SOS card, derived from xmage. Used solely as the validation oracle for the rewritten audited test suite — a test must pass against the matching Test Oracle Impl before it is committed. Never staged into agent runs.

*Avoid*: "reference implementation" (already names FDN learning material at `workspace/cards/fdn/{cn}/card_impl.py`), "gold impl"

**Test Oracle Workspace**

Host-side pre-built workspace at `benchmarks/sos/data/test_oracle_workspace/` that **mirrors **`benchmarks/sos/workspace/`** 1:1** — `engine/`, `cards/fdn/`, `cards/sos/` (with stubs for non-audited cards), `tests/`, `test_utils.py`, `AGENTS.md`, `pytest.ini`. Contains the Test Oracle Impls for every audited SOS card and an independent copy of `engine/` that may diverge from the canonical agent-visible engine. The oracle workspace's `test_utils.py` is the **home for the host-side ergonomic helpers** used by audited tests (`set_mana_pool`, `set_hand`, `set_battlefield`, `set_library_top`, `set_graveyard`, `assert_on_stack`, `assert_in_zone`, `assert_casting_error`) — there is no separate `silverquillm/test_utils.py`. Audited tests develop against this workspace and are copied to the canonical audited path at `benchmarks/sos/data/tests/audited/` once green. Never staged into agent runs; never seen by the agent. See ADR-010.

*Avoid*: "reference workspace" (reference is overloaded), "oracle" alone (ambiguous)

## Relationships

- A Benchmark Run evaluates one Agent Container (one agent + one model) against one Draft Set.
- A Benchmark Run launches one container session. The agent receives the full workload (all SOS cards) in a single Workspace.
- FDN cards are in-context examples (filled `card_impl.py` + colocated `tests.py` demonstrating the testing pattern). SOS cards are benchmark targets (SOS Card Stubs to fill in).
- Each agent produces `card_impl.py` per SOS card. In Tested Mode, also `tests.py` per card.
- The agent has a Writable Engine (`/workspace/engine/`) and may extend it freely throughout the run.
- All evaluation is post-run. After the container exits, the evaluator runs tests against harvested implementations and the final engine state.
- FDN Card Regression: evaluator runs `tests/audited/fdn/` against pre-filled FDN card impls + agent's final Writable Engine. Detects broken card behavior.
- Engine Regression: evaluator runs `tests/engine/` against agent's final Writable Engine. Detects broken rules mechanics.
- Cross-Eval and Self-Eval deferred to v2 (requires test harvester).
- The Base Set forms the reference codebase agents can browse. No Expanded Pool — agents implement new mechanics from scratch.
- A Draft Set may span multiple Scryfall set codes (e.g., FDN + SPG).
- Draft Set defines the card pool for Replay Validation (17lands replays are draft games).
- All card tests follow a uniform structure: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. FDN and SOS tests share this structure.
- The Base Set (FDN 001–291 + SPG 074–083) is validated via Replay Validation against 17lands GRE JSON data before scored benchmark runs.
- A Pipeline Validation Run precedes scored benchmark runs to verify the orchestration pipeline.
- Filesystem checks (does the file exist, does it differ from the template?) are the source of truth for agent output. Exit codes, stdout, and thinking traces are diagnostics only.
- `run_summary.json` is automatically generated after evaluation by aggregating per-card `result.json` files. The aggregator is a pure, idempotent function.
- The runner does NOT orchestrate test iteration — the agent self-manages. The runner stages, launches, harvests, evaluates.
- On container timeout, the runner harvests partial results. Completed cards are evaluated normally; unfinished cards scored as zero.
- Two benchmark modes: **Blind** (prompt omits test instructions) and **Tested** (prompt includes test instructions). Both produce `card_impl.py`. Distinction is prompt-only for v1. Compare modes via separate runs.
- SOS and FDN audited tests are evaluation-only artifacts — never staged in the agent's workspace, never in results directories. Engine tests are staged at `workspace/tests/engine/` per ADR-006 so agents can locally verify engine extensions; grading still uses host-repo copies for all three dimensions. FDN Reference Tests are colocated with the FDN card implementations at `workspace/cards/fdn/{collector_number}/tests.py` as additional reference for agents. Audited SOS grader tests live host-side only — there is no `workspace/tests/cards/` directory.
- The runner is the hard timeout authority. Agent Containers may read the Run Manifest for pacing, but correctness does not depend on honoring it.
- Output Snapshots are runner-owned, Workspace-only, and independent of Agent Container cooperation. The runner may use prior snapshot commits as fallback if final engine state is corrupted.
- The runner writes the User Prompt to `/workspace/prompt.md`; Agent Containers bake System Prompts into their entrypoints.
- Hard Timeout and Hang Timeout are independent — either can trigger `docker stop -t 10` to end a benchmark run.
- Test Oracle Workspace's `engine/` is independent of canonical `benchmarks/sos/workspace/engine/`. Canonical engine is frozen with respect to Phase 18 work to preserve cross-run benchmark comparability and to keep Engine Extension Quality scoring meaningful; engine extensions needed by Test Oracle Impls live in the oracle's engine only. See ADR-010.
- Audited tests call only public APIs present in the canonical engine. Tests never depend on extensions present in the Test Oracle Workspace's engine but absent from canonical — otherwise correct agent impls using different primitives would fail tests for non-correctness reasons.
- Audited tests are authored inside the Test Oracle Workspace mirror at `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_{cn}/tests.py` and copied to the canonical audited path at `benchmarks/sos/data/tests/audited/sos/sos_{cn}/tests.py` once green against the matching Test Oracle Impl. The canonical path is what the validation harness `tests/test_audited_against_reference.py` reads from when running against agent impls.
- Audited tests target observable game-state outcomes ("what the card does"), not card-text annotations ("what the card says"). Ability Words are not tested for presence; only the behavior described by the text following the ability word is asserted.
