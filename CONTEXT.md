# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs

use these terms exactly. Updated during grilling sessions.

## Terms

**Agent Container**

Docker image packaging a single coding agent with its CLI, entrypoint, mode (blind/tested), strategy, model selection, and prompt — the full benchmark configuration. The runner launches it with mounted volumes and API key env vars. The runner has zero knowledge of agent internals. Image name encodes the variant (e.g. `silverquillm-pi-blind:latest`).

*Avoid*: "agent adapter" (deprecated), "agent tool" (ambiguous)

**Audited Eval**

The only evaluation method in v1: audited tests run against agent output post-run. Three dimensions: target-set card correctness (SOS card correctness for SOS; HOB card correctness for the HOB-generation benchmarks), FDN card regression, engine regression. Tests are LLM-drafted, then failure-reviewed by a human. The authoritative measure of correctness.

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

Classification of card difficulty: trivial (1×), simple (2×), medium (3×), complex (4×), expert (5×). Assigned via automated heuristics. Recorded per card, but v1 leaderboard scoring is unweighted (raw pass/total) — complexity weighting is not applied in v1. Canonical key name in code and JSON is `complexity_tier` (not `tier`).

*Avoid*: "difficulty level", "tier" (as a standalone key name)

**Card Pool**

The set of target cards that make up one benchmark's problem set ("problem set" is the run-shape phrasing of the same thing). For SOS the Card Pool is the whole SOS Draft Set. The HOB benchmarks' Card Pools are three **selective subsets** of the HOB set — operator-picked, listed in HOB-BENCHMARKS.md, referenced by first-printing collector number — so Card Pool is no longer a synonym for Draft Set (grilling 2026-09-02).

*Avoid*: "target set" (deprecated — was ambiguous about whether it meant a single Scryfall set code or the full draft pool), "workload" (retired)

**Checkpoint (MSH)** *(retired — grilling 2026-08-27)*

Retired with the MSH benchmark: the checkpoint/capability-DAG design served bounded-context sequential implementation over a ~281-card pool; HOB problem sets (5–20 cards, one run) don't have that problem. Its design page (MSH-CHECKPOINTS.md) was deleted at grilling 2026-09-02 and survives only in git history. Was: a frozen, reference-validated snapshot of the whole MSH benchmark workspace taken after a card group — the unit of resume, regression attribution, and bounded per-step agent context.

*Avoid*: "Output Snapshot" (runner-owned 60-second Git commits), "snapshot" alone

**Candidate Bundle**

The self-contained directory artifact a Benchmark Candidate is exchanged as: the worker-type definition + resolved pins (base image digest, knowledge pin) + vendored knowledge tree + adapter identity, secret values excluded. Exported by the-ozolith's tooling; the only thing `silverquillm run --candidate <path>` accepts. Candidate identity = (base image digest, instruction hash, adapter identity), recomputed and verified from the bundle — never trusted from a recorded value. Adapter-agnostic by contract: the format never hardcodes the adapter set.

*Avoid*: "worker-type TOML" as the candidate input (a bare TOML is not self-contained — it references Config Repo siblings), "candidate config"

**Workload** *(retired — grilling 2026-08-27)*

Retired run-spec term. Formerly a card subset within a benchmark; killed because card subsets were a SOS-era hack that confuses benchmarks. One benchmark = one problem set; a run always consumes the whole set. The run spec is candidate + mode + benchmark + budget. Cheap pipeline validation uses a dedicated smoke benchmark (its own small problem set of validated FDN cards), never a subset of a real one.

*Avoid*: "workload", "card subset", "filtered run"

**Contamination**

When an LLM has seen target card implementations in its training data, invalidating the benchmark. Controlled via new set selection, no web access, and clean workspaces.

*Avoid*: "data leakage" (too generic)

**Test Harvester** *(manual v1 / automated v2)*

The mechanism for improving audited tests from harvested run results. **Manual v1**: the on-demand harvest script + combined investigation/discovery skill in [AUDITED-TEST-IMPROVEMENT-WORKFLOW.md](http://audited-test-improvement-workflow.md/) — a human reviews suspect tests (ranked by cross-impl failure breadth) and promotion candidates. **Automated v2** *(future)*: a pass that harvests Validated Results and scores audited test quality (cross-impl breadth, discrimination, convention-coupling) to surface suspect tests and promotion candidates with less human triage. Replaces the retired self-eval / N×N cross-eval framing; not run after Release.

*Avoid*: "cross-eval" / "self-eval" (retired N×N framing), "cross-validation" (overloaded ML term)

**Draft Set**

All cards contained in draft booster packs for a given MTG release. A Draft Set may span multiple Scryfall set codes. The SOS Draft Set = SOS base (cn 001–271). The FDN Draft Set = FDN 001–291 + SPG 074–083. The HOB set (`data/sets/hob.json`) is 321 printings of 193 unique cards — first printings at HOB 001–193, alternate printings at 194–321 — and the HOB benchmarks draw selective Card Pools from it rather than using the set whole (grilling 2026-09-02). Draft Set defines the card pool for Replay Validation because 17lands replays are from draft games.

*Avoid*: "target set" (deprecated), "set" alone (ambiguous — could mean a single Scryfall set code)

**DeterministicPlayer (SOS)**

The V1 / SOS-workspace test player, frozen with SOS. Driven by two explicit, separate, ordered channels: a **directive queue** (`script` — per-priority `no_op` / `perform_action` / `perform_illegal_action`, consumed each time the player holds priority under the Host-Side Driver) and a **choice script** (`choices` — the canonical answer deque the engine consumes via `choose_target` / `choose` / `choose_yes_no` / `choose_card` / `assign_damage_order` for decisions raised mid-cast / mid-resolution). Reproducible, no AI decision-making in v1; a dry queue on *either* channel fails the test (`ScriptExhaustedError`), never hangs or auto-passes. Player-initiated casts/activations carry their own targets on the directive; engine-initiated (triggered) objects pull targets/choices from the choice script.

*Avoid*: "test player", "mock player", using it unscoped — say DeterministicPlayer (SOS) or (V2); "(MSH)" as a scope marker (grilling 2026-08-27 — the engine generation outlives any one pool; V2 names the generation shared by all HOB tiers)

**DeterministicPlayer (V2)**

The V2 (HOB-generation) workspace's intent-driven test player — same class name as the SOS player by decision; the two live in per-benchmark workspaces that never import each other. Holds the test's active Intents, receives structured Player Queries from the engine, routes each query to an Intent by pattern-matching on source refs, and answers by preference over Player Decisions: greedy, first option that is both intended and valid in the implementation-provided order, no search. Queries matched by no card Intent fall to the Baseline Intent; matched by neither is an explicit failure. The SOS dry-script failure mode (ScriptExhaustedError) is replaced by boundary validation plus the "no offered option satisfies the intent" signal.

*Avoid*: "IntentPlayer" (rejected rename), "test player", "mock player", the SOS two-channel semantics (see DeterministicPlayer (SOS))

**Game Refs**

The dynamic extension of Game Symbols to all actual game objects — tokens, spells and abilities on the stack, etc. — tracked by the engine as objects are created. A Game Ref is hierarchical provenance (player / zone / card / object / ability); the object level carries the only opaque engine-minted identifier, the instance id, which tests never hardcode.

*Avoid*: "EngineRef" (working name), "object id" (only one field of a ref)

**Game Symbols**

The immutable, benchmark-owned vocabulary of Player Decision kinds and attribute values (the "blessed vocabulary"). Closed: tested agents cannot extend it; additions are benchmark-version events.

*Avoid*: "symbol" alone (collides with MTG mana symbols), "symbol set"

**Intent**

A test-scoped Player Query handler with an explicit lifecycle (`start_intent` → actions → `end_intent`, where its postcondition is checked). Answers whatever Player Queries an implementation raises by preference over Player Decisions — greedy, first intended-and-valid option, no search. Multiple Intents may be active; an always-active Baseline Intent supplies defaults for system-level queries. Audited-test-only — the engine is never intent-driven.

*Avoid*: "goal" / "policy" (rejected names), "answer script" (the V1 FIFO model this replaces)

**Modifiers**

Refinements riding on a Player Decision (spend restrictions, snow, doesn't-empty, …). Invisible to satisfaction matching; read only by engine predicates (e.g. spend-time checks) and audit assertions. Tested agents may add private Modifiers; Modifiers asserted on by audited tests must use canonical names.

*Avoid*: "tags" (working name)

**Output Snapshot**

Periodic runner-captured copy of the Workspace during an Agent Container run, roughly once per minute. Stored as host-side Git commits outside the container. Used for progress telemetry and as a fallback recovery point if final Workspace state is corrupted by timeout cutoff or broken engine edits.

*Avoid*: "checkpoint" (overloaded with spec checkpoints), "progress log" (that's `progress.jsonl`)

**Pipeline Validation Run**

A benchmark run whose purpose is to validate that the orchestration pipeline works end-to-end (workspace staging, container launch, result harvesting, evaluation). Not intended to produce meaningful scores — audited tests are not required. Precedes scored benchmark runs.

*Avoid*: "test run" (ambiguous), "dry run" (has a different meaning — `--dry-run` flag)

**Player Decision**

The immutable data struct representing one unit of choice offered in a Player Query: kind + attrs + Modifiers + an optional Game Ref. Pure data with zero behavior; satisfaction is subset matching on kind and attrs (a specific decision satisfies a more general one). Number decisions satisfy by exact equality.

*Avoid*: "Symbol" (working name), "option" alone (an option is a Player Decision inside a Query's options tuple)

**Player Query**

A question an engine raises to a player: source (set of Player Decisions identifying what raised it), human-readable prompt, an ordered options tuple of Player Decisions (the implementation-provided order is part of the contract), and min/max counts. `min=0` marks a legally declinable query.

*Avoid*: "Question" (working name), "prompt" alone (one field of a query)

**Replay Validation**

Engine correctness check that replays 17lands GRE (Game Rules Engine) state streams through the Python engine and verifies full game state at every GRE message boundary. Data source: 17lands pre-parsed GRE JSON — clean JSON files containing `GameStateType_Full` and `GameStateType_Diff` messages with object-level fidelity (zones, gameObjects by `grpId`/`instanceId`, life totals, annotations). Execution model: **observer mode** with state-diff comparison — seat 1 (17lands user) fully validated, seat 2 (opponent) actions oracle-injected from public game objects. Single parser, single format. See [17lands Replay Data Schema](https://www.notion.so/35b6a7adc8ed80978dccdf724213b6f8) and [ADR-003](https://www.notion.so/37a8b903f91b4309a15b91d149a90f7c).

*Avoid*: "differential testing" (deprecated XMage approach), "checkpoint validation" (we do full state comparison, not just EOT checkpoints), "aggregate CSV" (that's a different 17lands dataset)

**Resume Chain**

Sequence of Benchmark Runs linked via `resumed_from`, where each run after the first stages from the prior run's `workspace_final/`. Each leg is an independent Benchmark Run with its own `run_name`, results directory, Hard Timeout, snapshots, and evaluation. The chain is an audit-trail concept; the runner does not aggregate results across legs. CLI: `silverquillm resume <prior-run-id>`. See ADR-008.

*Avoid*: "session" (deprecated — too vague; use Resume Chain + Resume Leg), "continuation run"

**Resume Leg**

A Benchmark Run with `resumed_from` set — any run in a Resume Chain other than the first. Resume Legs are independent Benchmark Runs in every other respect (own results dir, own snapshots, own evaluation, own `run_summary.json`). Resume Legs are never leaderboard-valid: any run with `resumed_from` set has `leaderboard_valid = false` — they inherit prior-leg workspace state, so they are not head-to-head comparable with fresh full-set runs.

*Avoid*: "resumed session", "continuation run"

**Resume Preamble**

Extra lines the runner appends to the User Prompt when staging a Resume Leg. Always informs the agent (a) that this is a resume of `<prior-run-id>`, (b) that prior tests/implementations may already exist, and (c) that the workspace `.git` records prior commits. Conditional additional lines disclose (i) prior-run snapshot-fallback rollback when applicable, and (ii) image change when `--image` differs from the prior run's image. Image-agnostic — agents with no internal coordinator/cycle structure benefit equally.

*Avoid*: "resume notice", "resume header"

**Run Manifest**

Minimal runtime facts written by the runner to `/workspace/run_manifest.json` immediately before container launch. Contains only `timeout_seconds` and `deadline_utc`; it is advisory to the Agent Container and does not configure agent behavior.

*Avoid*: "config.json" (implies agent configuration), "agent config"

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

The per-benchmark directory at `benchmarks/<benchmark>/workspace/` in the bench repo (e.g. `benchmarks/sos/workspace/`, `benchmarks/hob-medium/workspace/`), copied wholesale to a per-run tmp path and mounted into the agent container at `/workspace/`. Contains the engine (canonical single copy, shared with bench tooling), all cards (FDN reference implementations + SOS Card Stubs), tests (`tests/conftest.py`, `tests/test_utils.py`, `tests/engine/`), agent-facing documentation (`AGENTS.md`, `PROJECT_MAP.md`, `rulebook.txt`), and supporting files (`pytest.ini`, `.gitignore`). Per-run files (`prompt.md`, `run_manifest.json`) are written into the copy at stage time, followed by an initial `git init && git commit` so the agent has clean version-control state. The resume staging variant (see Resume Chain) skips `git init` and preserves the prior run's `workspace_final/` `.git` history instead. The agent has read-write access to the entire workspace.

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

Task-specific instruction written by the runner to `/workspace/prompt.md` at staging time. Describes what the agent should implement (e.g., "Implement all SOS cards in `/workspace/cards/sos/`"). It lists the benchmark's whole target-card problem set — a Benchmark Run always stages the entire set; card-subset ("workload") runs are retired. Contrast with System Prompt.

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

**Benchmark Tier**

Lifecycle state of a benchmark controlling what may change, recorded in its benchmark config (`benchmarks/sos/config.json`). Three tiers with increasing lock scope: **Beta** (everything editable — `workspace/`, oracle impls/engine, audited tests), **Benchmarking** (`workspace/` locked; oracle impls/engine and audited tests still editable), **Released** (all three locked). Enforced by a CI check against the base branch's tier. Transitions are forward-only and non-reversible except for grave, documented reasons (Benchmarking→Beta invalidates all existing benchmarks; Released→Benchmarking retracts all published scores). SOS is currently in Benchmarking. Distinct from Complexity Tier — the config key here is `tier` scoped to the benchmark config, never the card-level `complexity_tier`. See ADR-011.

*Avoid*: "tier" alone (ambiguous with Complexity Tier — say "Benchmark Tier"), "benchmark state"

**Validated Results**

Per-run result artifacts committed under `docker/<image>/validated_results/<run-name>/`. Each run directory holds `eval_result.json` (aggregate pass/fail/total per card), a `cards/<card_id>/` subtree (`card_impl.py`, the exact `tests.py` used, and `result.json` with per-test failure node IDs and counts), plus logs, telemetry, `engine_diff.patch`, and manifests. The source corpus the harvest script reads.

*Avoid*: "results" alone (ambiguous with `results/{run_name}/` run output), "validated runs"

**Harvested Results**

The consolidated dataset produced by the harvest script from all Validated Results in the repo. Long-format JSONL — one row per `(image, run, card, test-node, pass/fail)`, fully denormalized, written in run-append order and grouped at query time (e.g. by `test_node`). Each row carries the `tests.py` content hash so audited-test changes across runs are detectable. Powers the combined investigation/discovery skill (the manual v1 Test Harvester).

*Avoid*: "harvest" alone, "test dump"

**Implementation-Agnostic Testing**

The core audited-test philosophy: a test asserts *what a card does* (observable game-state behavior) and must pass against *any* correct implementation — never coupling to one implementation's naming, internal structure, method names, or conventions. It discriminates correctness, not style: independent correct impls all pass, only genuinely wrong behavior fails. Operationalized by the behavioral/outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted audited tests (see [AUDITED-TEST-SUITE.md](http://audited-test-suite.md/)), and is the principle every test-improvement decision serves. The formalized, strengthened restatement of the Phase 18 behavioral-testing direction.

*Avoid*: "black-box testing" (narrower — only says don't read internals), "convention testing" / "naming-coupled tests" (the anti-pattern this rejects)

**Platform Tests**

Maintainer-authored tests for the SilverquiLLM repository's own tooling — runner, harvester, evaluator, telemetry, and `scripts/` — living under `tests/` (excluding `tests/audited/` and `tests/engine/`). They verify that the benchmark *software* works; they do not grade agent output. E.g. `tests/test_harvest_rows.py`, `tests/test_check_promotion_candidate.py`, `tests/test_evaluator.py`. Distinct from Audited Tests, Engine Tests, and Agent Tests.

*Avoid*: "repository tests" (ambiguous — Audited Tests and Engine Tests also live in the repo), "unit tests" alone (some are integration-level), "harness tests" (collides with the audited validation harness)

**Audited Tests**

The curated, human-reviewed grading suite at `tests/audited/{set_code}/{collector_number}/tests.py`, used by Audited Eval to score agent output. Behavioral / outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted (Implementation-Agnostic Testing). Maintainer-authored; each test must pass against the matching Test Oracle Impl before commit. Covers the SOS Card Correctness and FDN Card Regression dimensions. Distinct from Engine Tests, Agent Tests, and FDN Reference Tests.

*Avoid*: "gold tests", "grader tests" (informal — say "Audited Tests"), "benchmark tests"

**Engine Tests**

Maintainer-authored core MTG-engine mechanics tests at `tests/engine/` — the input to the Engine Regression evaluation dimension (mana, stack, combat, state-based actions, etc.), run against the agent's final Writable Engine post-run. Staged into `workspace/tests/engine/` per ADR-006 so agents can self-verify Engine Extensions, but grading uses the host-repo copy. A separate bucket from Audited Tests (which grade card behavior) and Platform Tests (which test the tooling).

*Avoid*: "engine test" alone (ambiguous — say "Engine Tests" / "Engine Regression"), folding under "audited tests"

**Agent Tests**

The `tests.py` files a coding agent writes during a Tested Mode run — one per card, alongside its `card_impl.py`. Harvested as artifacts in Validated Results but never used for v1 scoring (Audited Tests are the grader). The raw source the Test Harvester mines for promotion candidates. Distinct from Audited Tests (the grading suite) and FDN Reference Tests (agent-visible learning material).

*Avoid*: "benchmark tests" (ambiguous — "benchmark" already names Run/Tier/Mode, and Audited Tests also serve the benchmark), "candidate tests" (reserve for promotion candidates mined from Agent Tests), "harvested tests" (Harvested Results is the post-harvest dataset; pre-harvest these are Agent Tests)

**Audited Test API**

The single sanctioned interface audited tests use to touch the engine, specified in [AUDITED-TEST-API.md](http://audited-test-api.md/). Four parts: set up (`set_board_state` / `PermanentSpec`), advance (Host-Side Driver `priority_loop` + sparing `advance_to_phase`), `DeterministicPlayer` directives (`CastSpell` / `CastSpellFree` / `ActivateAbility` / `PlayLand`), and `assert_*` observations. References only canonical-engine primitives and *composes or duplicates* canonical behavior (e.g. `cast_spell_from_exile` for alt-zone casts); building and using it requires no change to any workspace engine. The tests it drives still run against the oracle and each candidate engine, which may diverge — only the test *result* depends on the engine.

*Avoid*: "test harness" (collides with the validation harness `tests/test_audited_against_reference.py`), "test_utils" alone (that is one module within the API)

**Host-Side Driver**

The `priority_loop(game)` advancer audited tests use to move the game forward by polling players for directives in APNAP order — not the engine's own all-pass auto-drain. Each iteration: check state-based actions, place triggered abilities, poll for one directive (retain-on-action), and if no one acts resolve **exactly one** stack object via `resolve_top`. Single-step resolution keeps every resolution observable; a dry directive queue or choice script raises `ScriptExhaustedError` (test fails, never hangs). Contrast `advance_to_phase`, which fast-forwards turn structure — processing turn-based actions, triggers, and end-of-turn cleanup but opening no priority windows (a triggered ability that forces a choice is still answered from the choice script).

*Avoid*: "game loop" / "run loop" (`game.run()` is banned in audited tests), "auto-drain" (that is the engine's loop, which this replaces)

## Relationships

- A Benchmark Run evaluates one Agent Container (one agent + one model) against one benchmark's Card Pool — the whole SOS Draft Set for SOS, a selective HOB subset for each HOB benchmark.
- A Benchmark Run launches one container session. The agent receives the benchmark's entire problem set (every target card) in a single Workspace — one benchmark = one problem set; there is no card-subset "workload" notion (grilling 2026-08-27).
- FDN cards are in-context examples (filled `card_impl.py` + colocated `tests.py` demonstrating the testing pattern). SOS cards are benchmark targets (SOS Card Stubs to fill in).
- Each agent produces `card_impl.py` per SOS card. In Tested Mode, also `tests.py` per card.
- The agent has a Writable Engine (`/workspace/engine/`) and may extend it freely throughout the run.
- All evaluation is post-run. After the container exits, the evaluator runs tests against harvested implementations and the final engine state.
- FDN Card Regression: evaluator runs `tests/audited/fdn/` against pre-filled FDN card impls + agent's final Writable Engine. Detects broken card behavior.
- Engine Regression: evaluator runs `tests/engine/` against agent's final Writable Engine. Detects broken rules mechanics.
- Self-eval / N×N cross-eval are retired; the Test Harvester (manual v1, automated v2) improves audited tests instead. Automated v2 test-quality scoring is future work.
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
- The Audited Test API is the only sanctioned way an audited test touches the engine. It references only canonical-engine primitives and composes or duplicates canonical behavior (e.g. `cast_spell_from_exile` for alt-zone casts); building and using it requires no change to any workspace engine.
- The Host-Side Driver (`priority_loop`) advances audited tests by polling DeterministicPlayers for directives and resolving one stack object at a time; `advance_to_phase` fast-forwards turn structure (turn-based actions, triggers, end-of-turn cleanup) without opening priority windows, though a triggered ability that forces a choice is still answered from the choice script.
- Audited tests import whatever engine they run on (`engine.*` — the oracle during validation, the candidate during evaluation); portability comes from every candidate implementing the canonical public API, not from restricting imports. The paradigm forbids private-attribute poking (`_script`, `_resolve_targets`), not engine imports.
- Mechanics absent from the canonical engine (sos_57 `mana_spent` refund, sos_226 casualty, sos_201 miracle, sos_245 affinity, sos_1 / sos_120 graveyard→exile redirect, sos_97 coin-flip RNG) are exercised indirectly through canonical entrypoints + observable-state assertions, with RNG made deterministic test-side via seed-replacement (`game.rng = random.Random(seed)`); no mechanic-specific test-API support and no engine change.
- Player-initiated casts/activations carry their targets on the directive; engine-initiated (triggered) objects take no directive and pull targets/choices from the choice script. `ActivateAbility` names the ability by its index into `get_activated_abilities()` / `get_loyalty_abilities()` (printed order).
