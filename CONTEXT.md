# SilverquiLLM-bench — Domain Glossary

Canonical terms for this project. Coding agents and specs use these terms exactly. Updated during grilling sessions.

## Terms

**Ability Word**

Italicized flavor label printed on a card naming a triggered or static effect (e.g. Converge, Prepared, Opus, Paradigm, Landfall, Heroic). Has no inherent rules meaning — the actual rules text follows the label and produces the behavior. Tests target the behavior described by that text, never the label itself.

_Avoid_: "keyword" (Ability Words are not Keyword Abilities), "flag", "tag"

**Agent Container** *(legacy image-based candidate)*

Docker image packaging a single coding agent with its CLI, entrypoint, mode (blind/tested), strategy, model selection, and prompt — the full benchmark configuration. The runner launches it with mounted volumes and API key env vars. The runner has zero knowledge of agent internals. Image name encodes the variant (e.g. `silverquillm-pi-blind:latest`).

_Avoid_: "agent adapter" (deprecated), "agent tool" (ambiguous)

**Agent Tests**

The `tests.py` files a coding agent writes during a Tested Mode run — one per card, alongside its `card_impl.py`. Harvested as artifacts in Validated Results but never used for v1 scoring (Audited Tests are the grader). The raw source the Test Harvester mines for promotion candidates. Distinct from Audited Tests (the grading suite) and FDN Reference Tests (agent-visible learning material).

_Avoid_: "benchmark tests" (ambiguous — "benchmark" already names Run/Tier/Mode, and Audited Tests also serve the benchmark), "candidate tests" (reserve for promotion candidates mined from Agent Tests), "harvested tests" (Harvested Results is the post-harvest dataset; pre-harvest these are Agent Tests)

**Agent Turn**

One model response or one tool call made during a Benchmark Run, including descendant-agent work.
The total combines both kinds of event; response and tool-call counts remain separately observable (grilling 2026-09-26).

_Avoid_: "Codex turn" (one native user request can contain many Agent Turns), "tool call" as a synonym for the total

**Audited Engine Tests**

The hidden Audited Tests suite for the Engine Regression dimension, at a benchmark's `data/tests/audited/engine/` (grilling 2026-10-02).
Seeded from the Engine Reference Tests, then maintained independently of them; it asserts rules-correct engine behavior through the Audited Test API.

_Avoid_: "engine tests" alone, "hidden engine tests" (informal)

**Audited Eval**

The only evaluation method in v1: audited tests run against agent output post-run. Three dimensions: target-set card correctness (SOS card correctness for SOS; HOB card correctness for the HOB-generation benchmarks), FDN card regression, engine regression. Tests are LLM-drafted, then failure-reviewed by a human. The authoritative measure of correctness.

_Avoid_: "gold eval", "human eval"

**Audited Test API**

The single sanctioned interface audited tests use to touch the engine, specified in [AUDITED-TEST-API.md](docs/specs/AUDITED-TEST-API.md). Four parts: set up (`set_board_state` / `PermanentSpec`), advance (Host-Side Driver `priority_loop` + sparing `advance_to_phase`), `DeterministicPlayer` directives (`CastSpell` / `CastSpellFree` / `ActivateAbility` / `PlayLand`), and `assert_*` observations. References only canonical-engine primitives and *composes or duplicates* canonical behavior (e.g. `cast_spell_from_exile` for alt-zone casts); building and using it requires no change to any workspace engine. The tests it drives still run against the oracle and each candidate engine, which may diverge — only the test *result* depends on the engine.

_Avoid_: "test harness" (collides with the validation harness `tests/test_audited_against_reference.py`), "test_utils" alone (that is one module within the API)

**Audited Tests**

The curated, human-reviewed, hidden grading suites under a benchmark's `data/tests/audited/`, used by Audited Eval to score agent output. Behavioral / outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted (Implementation-Agnostic Testing). Maintainer-authored; each test must pass against the matching Test Oracle Impl before commit. Covers all three dimensions: target-card tests, FDN tests, and Audited Engine Tests (grilling 2026-10-02).
They assert rules-correct behavior, so a baseline engine carrying Known Defects fails some of them.
Distinct from Reference Tests, Agent Tests, and Platform Tests.

_Avoid_: "gold tests", "grader tests" (informal — say "Audited Tests"), "benchmark tests"

**Base Set**

The FDN Draft Set — the MTG Foundations limited format card pool (FDN 001–291 + SPG 074–083 Special Guests) — plus three supporting FDN cards outside it that Audited Tests need to reach positions no Draft Set card reaches: Basilisk Collar (669), Demolition Field (687) and Confiscate (709) (grilling 2026-10-05). Serves as engine validation, agent reference examples, and regression suite. Ported from XMage Java source. Engine validated via Replay Validation against 17lands GRE JSON data.

_Avoid_: "foundation cards" (use "Foundations cards" or "base set")

**Baseline Score**

The Combined Regression score an unmodified benchmark Workspace earns (grilling 2026-10-02).
It is below the Known-Best Score by exactly the tests the benchmark's Known Defects make fail, and it changes whenever those Audited Tests change.

_Avoid_: "zero point", "floor" (an agent can score below it by regressing)

**Batch**

One file `batches/<id>.toml` in the bench repo's batch queue: an optional `not_before` (RFC 3339 with an offset) plus an ordered list of run specs (Karn build output + construct + benchmark, with an optional Login Profile and budget). Historical Candidate Bundle batches (candidate ref + mode) are unsupported and never run. Desired state, authored and edited by the operator, never written by the scheduler; the scheduler's observed state (pending / running / done / failed per started run, with the identity resolved at run start) lives beside it in `batches/state/` — portable, committed by the operator as checkpoints, never carrying a host-local detail. The id is a permanent, one-shot identifier (its state file is the record of what ran under it; never reused). A Batch with no committed state is blocked until the operator acknowledges starting it from entry zero. Batches execute serially in name order; edits to a running Batch affect only not-yet-started runs; a failed run continues the Batch (#66).

_Avoid_: "job" (the substrate's job dir is a different concept), "queue entry" for the file (a Batch holds several runs)

**Benchmark Candidate**

An executable agent configuration selected for evaluation.
For Karn, the candidate is an immutable image paired with the Construct Definition, version 4 or 5, that selects its runtime behavior (grilling 2026-09-26).
Legacy candidates retain their historical representation and identity.

_Avoid_: "recipe" or "image tag" as the complete candidate identity

**Benchmark Mode** *(historical run parameter)*

A bench-owned task-presentation variant recorded by historical runs, independently of candidate identity.
New Karn runs take their planning and task guidance from the selected benchmark, without a separate basic/planned selector (grilling 2026-09-26).

_Avoid_: "execution mode" (Automaton versus Vehicle is an upstream distinction), "strategy" (candidate behavior)

**Benchmark Run**

One budgeted execution of a Benchmark Candidate against a benchmark's entire Card Pool and instruction data, followed by harvesting and Audited Eval.
Each run has its own observations and results, including when it belongs to a Resume Chain.

_Avoid_: "workload" (retired), "session" (ambiguous)

**Benchmark Tier**

Lifecycle state of a benchmark controlling what may change, recorded in its benchmark config (`benchmarks/sos/config.json`). Three tiers with increasing lock scope: **Beta** (everything editable — `workspace/`, oracle impls/engine, audited tests), **Benchmarking** (`workspace/` locked; oracle impls/engine and audited tests still editable), **Released** (all three locked). Enforced by a CI check against the base branch's tier. Transitions are forward-only and non-reversible except for grave, documented reasons (Benchmarking→Beta invalidates all existing benchmarks; Released→Benchmarking retracts all published scores). SOS and hob-medium are Released. Distinct from Complexity Tier — the config key here is `tier` scoped to the benchmark config, never the card-level `complexity_tier`. See ADR-011.

_Avoid_: "tier" alone (ambiguous with Complexity Tier — say "Benchmark Tier"), "benchmark state"

**Blind Mode**

Benchmark mode (`MODE=blind`) where the prompt does not instruct the agent to write or run tests. The agent still has access to pytest — the distinction is prompt-only for v1. Produces `card_impl.py` per card. Compare against Tested Mode via separate runs.

_Avoid_: "blind implementation" as a noun (deprecated — was `blind_impl.py`)

**Candidate Bundle** *(legacy interchange format)*

The self-contained directory artifact a Benchmark Candidate is exchanged as: the worker-type definition + resolved pins (base image digest, knowledge pin) + vendored knowledge tree + adapter identity, secret values excluded. Exported by the-ozolith's tooling (`theozolith candidate export`: `candidate.json` + generated `Dockerfile` + compiled knowledge tree + baked policy tree; `docs/specs/BENCH-CONTRACT.md`, `bundle_format_version` 2); historically the only thing the removed Candidate Bundle run path accepted. Candidate Bundles are no longer executed; each historical `ozolith-v1` Run Record carries its vendored bundle. Candidate identity = (base image digest, instruction hash, adapter identity), recomputed and verified from the bundle by TheOzolith's verifier (`silverquillm.candidate` consumes `verify_bundle`; the bench never reimplements the hash) — never trusted from a recorded value: a bundle whose recorded identity, or whose directory-name suffix, disagrees with the recomputed one is a hard refusal, as is a bundle carrying a secret value (#65). Adapter-agnostic by contract: the format never hardcodes the adapter set, and neither does the bench.

_Avoid_: "worker-type TOML" as the candidate input (a bare TOML is not self-contained — it references Config Repo siblings), "candidate config"

**Candidate Hash**

The bench's key for a verified candidate: the SHA-256 of the canonical JSON of the whole identity triple `{"adapter", "base_digest", "instruction_hash"}` (`silverquillm.results_repo.candidate_hash`; the-ozolith's canonical identity omits the adapter name, so the instruction hash alone is not injective over the triple). Names `results/<candidate-hash>/` in the Results Repo and, as its first eight characters (`hash8`), the `candidates/<slug>--<hash8>/` directory of a checked-in candidate (#39 §4: identity-hash suffix, flat, deduplicating). A recorded value everywhere it appears: recomputed on every run and every test run.

_Avoid_: "identity hash" for this key (the-ozolith's identity spec uses that phrase for the instruction hash), "candidate id"

**Card Pool**

The set of target cards that make up one benchmark's problem set ("problem set" is the run-shape phrasing of the same thing). For SOS the Card Pool is the whole SOS Draft Set. The HOB benchmarks' Card Pools are three **selective subsets** of the HOB set — operator-picked, listed in HOB-BENCHMARKS.md, referenced by first-printing collector number — so Card Pool is no longer a synonym for Draft Set (grilling 2026-09-02).

_Avoid_: "target set" (deprecated — was ambiguous about whether it meant a single Scryfall set code or the full draft pool), "workload" (retired)

**Card Spec**

JSON file (`card_spec.json`) containing a card's name, mana cost, type line, and oracle text. The only card-specific input provided to the agent.

_Avoid_: "card data", "card definition"

**Checkpoint (MSH)** *(retired — grilling 2026-08-27)*

Retired with the MSH benchmark: the checkpoint/capability-DAG design served bounded-context sequential implementation over a ~281-card pool; HOB problem sets (5–23 cards, one run) don't have that problem. Was: a frozen, reference-validated snapshot of the whole MSH benchmark workspace taken after a card group — the unit of resume, regression attribution, and bounded per-step agent context.

_Avoid_: "Output Snapshot" (runner-owned 60-second Git commits), "snapshot" alone

**Combined Regression**

The pooled FDN Card Regression and Engine Regression Audited Tests of a benchmark, reported as one raw pass/total with its Baseline Score, Known-Best Score, Fixed and Regressed counts (grilling 2026-10-02).
The two regression dimensions it pools keep their own raw pass/total for diagnosis.

_Avoid_: "regression score" alone (ambiguous with either dimension), "total regression"

**Complexity Tier**

Classification of card difficulty: trivial (1×), simple (2×), medium (3×), complex (4×), expert (5×). Assigned via automated heuristics. Recorded per card, but v1 leaderboard scoring is unweighted (raw pass/total) — complexity weighting is not applied in v1. Canonical key name in code and JSON is `complexity_tier` (not `tier`).

_Avoid_: "difficulty level", "tier" (as a standalone key name)

**Construct Definition**

The Karn-owned artifact binding an immutable image to its declared execution behavior and required runtime facilities.
Distinct Construct Definitions may select the same image.

_Avoid_: "Candidate Bundle" (the historical interchange format), "image" alone

**Contamination**

When an LLM has seen target card implementations in its training data, invalidating the benchmark. Controlled via new set selection, no web access, and clean workspaces.

_Avoid_: "data leakage" (too generic)

**DeterministicPlayer (SOS)**

The V1 / SOS-workspace test player, frozen with SOS. Driven by two explicit, separate, ordered channels: a **directive queue** (`script` — per-priority `no_op` / `perform_action` / `perform_illegal_action`, consumed each time the player holds priority under the Host-Side Driver) and a **choice script** (`choices` — the canonical answer deque the engine consumes via `choose_target` / `choose` / `choose_yes_no` / `choose_card` / `assign_damage_order` for decisions raised mid-cast / mid-resolution). Reproducible, no AI decision-making in v1; a dry queue on *either* channel fails the test (`ScriptExhaustedError`), never hangs or auto-passes. Player-initiated casts/activations carry their own targets on the directive; engine-initiated (triggered) objects pull targets/choices from the choice script.

_Avoid_: "test player", "mock player", using it unscoped — say DeterministicPlayer (SOS) or (V2); "(MSH)" as a scope marker (grilling 2026-08-27 — the engine generation outlives any one pool; V2 names the generation shared by all HOB tiers)

**DeterministicPlayer (V2)**

The V2 (HOB-generation) workspace's intent-driven test player — same class name as the SOS player by decision; the two live in per-benchmark workspaces that never import each other. Holds the test's active Intents, receives structured Player Queries from the engine, routes each query to an Intent by pattern-matching on source refs, and answers by preference over Player Decisions: greedy and preference-major — each preference in rank order takes the first offered option satisfying it — no search. Queries matched by no card Intent fall to the Baseline Intent; matched by neither is an explicit failure. The SOS dry-script failure mode (ScriptExhaustedError) is replaced by boundary validation plus the "no offered option satisfies the intent" signal.
From fra-hard-v2 onward it answers every query from its player's script of Script Entries instead of Intents, and play stops when a script runs out (grilling 2026-10-05).

_Avoid_: "IntentPlayer" (rejected rename), "test player", "mock player", the SOS two-channel semantics (see DeterministicPlayer (SOS))

**Draft Set**

All cards contained in draft booster packs for a given MTG release. A Draft Set may span multiple Scryfall set codes. The SOS Draft Set = SOS base (cn 001–271). The FDN Draft Set = FDN 001–291 + SPG 074–083. The HOB set (`data/sets/hob.json`) is 321 printings of 193 unique cards — first printings at HOB 001–193, alternate printings at 194–321 — and the HOB benchmarks draw selective Card Pools from it rather than using the set whole (grilling 2026-09-02). Draft Set defines the card pool for Replay Validation because 17lands replays are from draft games.

_Avoid_: "target set" (deprecated), "set" alone (ambiguous — could mean a single Scryfall set code)

**Engine Extension**

Modification or addition to `engine/` files by the agent during a benchmark run. Expected when a card requires a mechanic not yet supported. Good extensions are generic (reusable by future cards); bad extensions are card-specific hacks that break other cards.

_Avoid_: "engine modification" (neutral — use "engine extension" to imply additive/constructive intent)

**Engine Regression**

Post-run evaluation dimension: Audited Engine Tests run against the agent's final Writable Engine. Detects whether engine extensions broke fundamental game mechanics (mana, stack, combat, state-based actions, etc.) and whether Known Defects were fixed. Pooled into Combined Regression (grilling 2026-10-02). Separate from FDN Card Regression — an agent could pass all FDN card tests but fail engine tests if card-level workarounds corrupt internal state.

_Avoid_: "engine test" alone (ambiguous — say "Audited Engine Tests" or "Engine Reference Tests")

**Engine Reference Tests**

The agent-visible core MTG-engine mechanics tests at `workspace/engine_tests/` (mana, stack, combat, state-based actions, etc.), staged so agents can check their Engine Extensions locally (ADR-006).
Like FDN Reference Tests they are editable and never graded, and they may be wrong or encode a Known Defect (grilling 2026-10-02).
The graded counterpart is the hidden Audited Engine Tests suite.

_Avoid_: "Engine Tests" alone (formerly named both the visible and the graded suite), "engine test" alone

**Estimated Cost**

The API-equivalent USD estimate of a Benchmark Run's observed model usage under a recorded pricing basis.
It supports resource-use comparisons and does not represent the actual subscription charge attributable to the run (grilling 2026-09-26).

_Avoid_: "billed cost", "subscription cost" for this estimate

**Estimated Weekly Usage**

The share of one Login Profile's weekly subscription allowance that is used up, as the operator monitor estimates it (grilling 2026-10-07).
It starts from the provider's own newest usage reading for that Login Profile while that reading's weekly window lasts, and adds Estimated Cost observed since, converted at a host-configured provider rate.
For one week after the reading's reset it counts Estimated Cost from the reset; past that, or with no reading, it counts the last seven days' Estimated Cost.
It is an operating aid, not a measurement of any Benchmark Run.

_Avoid_: "quota", "credits", "credential slot usage"

**Exclusion**

A Results Repo entry that leaves one Run Record out of analyses, naming a reason code and a note, without changing the record.
A rule excludes a run on an observed fact, such as zero Agent Turns or subagent use; an operator excludes anything a rule cannot see, and a superseded run names the record that replaces it.

_Avoid_: "rejected run", "invalid run" (the record stays valid evidence), "filtered out" for an ad hoc analysis choice

**FDN Card Regression**

Post-run evaluation dimension: FDN audited tests (`tests/audited/fdn/`) run against pre-filled FDN `card_impl.py` files using the agent's final Writable Engine. Detects whether engine extensions broke existing card behavior and whether Known Defects were fixed. Pooled into Combined Regression (grilling 2026-10-02). Host-side only; not staged into the Workspace. Distinct from FDN Reference Tests.

_Avoid_: "regression check" (deprecated — was per-card sequential re-run), "FDN tests" alone (ambiguous — specify Reference vs Card Regression)

**FDN Reference Tests**

Illustrative pytest files colocated with FDN reference implementations at `cards/fdn/{collector_number}/tests.py`. Agent-visible inside the Workspace. Demonstrate the testing pattern (DeterministicPlayer scripts, expected-state asserts) so agents can model `cards/sos/{card_id}/tests.py` after them in Tested Mode. Distinct from FDN Card Regression — these are learning material, not grading input. One kind of Reference Tests: editable, and may be wrong (grilling 2026-10-02).

_Avoid_: "FDN tests" alone (ambiguous — specify Reference vs Card Regression), "FDN illustrative tests" (use "FDN Reference Tests")

**Game Refs**

The dynamic extension of Game Symbols to all actual game objects — tokens, spells and abilities on the stack, etc. — tracked by the engine as objects are created. A Game Ref is hierarchical provenance (player / zone / card / object / ability); the object level carries the only opaque engine-minted identifier, the instance id, which tests never hardcode.

_Avoid_: "EngineRef" (working name), "object id" (only one field of a ref)

**Game Symbols**

The immutable, benchmark-owned vocabulary of Player Decision kinds and attribute values (the "blessed vocabulary"). Closed: tested agents cannot extend it; additions are benchmark-version events.

_Avoid_: "symbol" alone (collides with MTG mana symbols), "symbol set"

**Grader Container**

The network-less, bench-owned container in which every grading pass and engine-viability probe runs the candidate's code, so candidate code never executes on the benchmark host.
It protects the host, not the integrity of the candidate's own score.

**Hang Timeout**

Secondary timeout that triggers when no monitored file activity (Docker pipe output, `/output/` files) occurs for a configurable period during a benchmark run. Catches catastrophic agent failures (process death, API outage, infinite loops) without false-positiving on long thinking pauses. CLI flag: `--hang-timeout`.

_Avoid_: "idle timeout" (implies workspace-only activity check)

**Hard Timeout**

Overall wall-clock time limit for a benchmark run, enforced by the runner via monotonic clock check in the main poll loop. The runner writes `timeout_seconds` and `deadline_utc` to the Run Manifest before launch and stops the container when the deadline passes. CLI flag: `--timeout`.

_Avoid_: "container timeout" (ambiguous — could mean Docker's `--stop-timeout` grace period)

**Harvested Results**

The consolidated dataset produced by the harvest script from all Validated Results in the repo. Long-format JSONL — one row per `(image, run, card, test-node, pass/fail)`, fully denormalized, written in run-append order and grouped at query time (e.g. by `test_node`). Each row carries the `tests.py` content hash so audited-test changes across runs are detectable. Powers the combined investigation/discovery skill (the manual v1 Test Harvester).

_Avoid_: "harvest" alone, "test dump"

**Host-Side Driver**

The `priority_loop(game)` advancer audited tests use to move the game forward by polling players for directives in APNAP order — not the engine's own all-pass auto-drain. Each iteration: check state-based actions, place triggered abilities, poll for one directive (retain-on-action), and if no one acts resolve **exactly one** stack object via `resolve_top`. Single-step resolution keeps every resolution observable; a dry directive queue or choice script raises `ScriptExhaustedError` (test fails, never hangs). Contrast `advance_to_phase`, which fast-forwards turn structure — processing turn-based actions, triggers, and end-of-turn cleanup but opening no priority windows (a triggered ability that forces a choice is still answered from the choice script).

_Avoid_: "game loop" / "run loop" (`game.run()` is banned in audited tests), "auto-drain" (that is the engine's loop, which this replaces)

**Implementation-Agnostic Testing**

The core audited-test philosophy: a test asserts *what a card does* (observable game-state behavior) and must pass against *any* correct implementation — never coupling to one implementation's naming, internal structure, method names, or conventions. It discriminates correctness, not style: independent correct impls all pass, only genuinely wrong behavior fails. Operationalized by the behavioral/outcome-based, canonical-engine-API-only, `DeterministicPlayer`-scripted audited tests (see [AUDITED-TEST-SUITE.md](docs/specs/AUDITED-TEST-SUITE.md)), and is the principle every test-improvement decision serves. The formalized, strengthened restatement of the Phase 18 behavioral-testing direction.

_Avoid_: "black-box testing" (narrower — only says don't read internals), "convention testing" / "naming-coupled tests" (the anti-pattern this rejects)

**Intent**

A test-scoped Player Query handler with an explicit lifecycle (`start_intent` → actions → `end_intent`, where its postcondition is checked). Answers whatever Player Queries an implementation raises by preference over Player Decisions — greedy and preference-major: each preference in rank order takes the first offered option satisfying it, no search. Multiple Intents may be active; an always-active Baseline Intent supplies defaults for system-level queries. Audited-test-only — the engine is never intent-driven. HOB benchmarks only: from fra-hard-v2 onward each player's Script Entries answer every query (grilling 2026-10-05).

_Avoid_: "goal" / "policy" (rejected names), "answer script" (the V1 FIFO model this replaces)

**Karn**

The builder that resolves Construct recipes and produces the images, Construct Definitions, and plugins used by a Benchmark Candidate.
Karn is independent of Ozolith's runtime manager.
SilverquiLLM takes only the construct contract from Karn and runs a completed build by itself.

_Avoid_: "Ozolith" when referring to candidate building

**Keyword Ability**

MTG rules construct the engine implements (e.g. Flying, Reach, Deathtouch, Affinity, Casualty, Cascade, the Miracle keyword). Cards with a Keyword Ability inherit its rules text by reference. Tests probe the behavior produced by the keyword, not just presence in a `keywords[]` list.

_Avoid_: "ability word" (distinct concept — see Ability Word)

**Known Defect**

A recorded way a benchmark's baseline engine or FDN implementations depart from `RULEBOOK.txt`, listed with its rule citation and the Audited Tests it makes fail (grilling 2026-10-02).
A Known Defect is either inherited (found in an engine or implementation) or a Seeded Defect; agents may fix either kind.

_Avoid_: "bug" alone, "baseline gap" (the retired name for failing cases cut from a graded suite)

**Known-Best Engine**

The engine with every engine Known Defect fixed, kept in the Known-Best Workspace and separate from every benchmark Workspace (grilling 2026-10-02).
Benchmark baselines and Test Oracle Workspace engines are ported from it; fixes land in it first.

_Avoid_: "reference engine", "canonical engine" (the canonical engine is a benchmark's agent-visible baseline), "gold engine"

**Known-Best Score**

The Combined Regression score the Known-Best Engine earns: always a perfect score, which validates that every regression Audited Test is passable (grilling 2026-10-02).

_Avoid_: "max score", "oracle score"

**Known-Best Workspace**

The host-only, benchmark-independent workspace holding the Known-Best Engine, the FDN implementations with every Known Defect fixed, and the full regression Audited Tests (grilling 2026-10-02).
A benchmark is built by porting a copy of it.

_Avoid_: "master workspace", "reference workspace"

**Login Pool**

The host-local set of Login Profiles enrolled through one login plugin, such as every Claude subscription login on the host.
A run takes any free profile from its candidate's pool, so the number of profiles is the number of runs that provider can serve at once (grilling 2026-09-28).

_Avoid_: "credential pool" (a profile holds one login, never a copied credential)

**Login Profile**

One host-local subscription login in a Login Pool, through which a run authenticates independently of Benchmark Candidate identity.
Any candidate using the pool's login plugin may use any of its profiles, and only one run uses a profile at a time on the host (grilling 2026-09-26; pooled grilling 2026-09-28).

_Avoid_: "candidate credential" (authentication is not candidate identity)

**Modifiers**

Refinements riding on a Player Decision (spend restrictions, snow, doesn't-empty, …). Invisible to satisfaction matching; read only by engine predicates (e.g. spend-time checks) and audit assertions. Tested agents may add private Modifiers; Modifiers asserted on by audited tests must use canonical names.

_Avoid_: "tags" (working name)

**Output Snapshot**

A periodic runner-retained copy of the Workspace during a Benchmark Run, used as progress evidence and a possible fallback for grading.
Karn retains copies with content digests and capture times under the [Karn Benchmark Contract](docs/specs/KARN-BENCHMARK-CONTRACT.md#operator-entrypoints-and-records); historical image runs stored snapshots as host-side Git commits.

_Avoid_: "checkpoint" (overloaded with spec checkpoints), "progress log" (that's `progress.jsonl`)

**Pipeline Validation Run**

A benchmark run whose purpose is to validate that the orchestration pipeline works end-to-end (workspace staging, container launch, result harvesting, evaluation). Not intended to produce meaningful scores — audited tests are not required. Precedes scored benchmark runs.

_Avoid_: "test run" (ambiguous), "dry run" (has a different meaning — `--dry-run` flag)

**Platform Tests**

Maintainer-authored tests for the SilverquiLLM repository's own tooling — runner, harvester, evaluator, telemetry, and `scripts/` — living under the repository's top-level `tests/` (the grading suites live elsewhere: Audited Tests under `benchmarks/<benchmark>/data/tests/audited/`, Reference Tests in the benchmark's `workspace/`). They verify that the benchmark *software* works; they do not grade agent output. E.g. `tests/test_harvest_rows.py`, `tests/test_check_promotion_candidate.py`, `tests/test_evaluator.py`. Distinct from Audited Tests, Reference Tests, and Agent Tests.

_Avoid_: "repository tests" (ambiguous — Audited Tests and Reference Tests also live in the repo), "unit tests" alone (some are integration-level), "harness tests" (collides with the audited validation harness)

**Player Decision**

The immutable data struct representing one unit of choice offered in a Player Query: kind + attrs + Modifiers + an optional Game Ref. Pure data with zero behavior; satisfaction is subset matching on kind and attrs (a specific decision satisfies a more general one). Number decisions satisfy by exact equality.

_Avoid_: "Symbol" (working name), "option" alone (an option is a Player Decision inside a Query's options tuple)

**Player Query**

A question an engine raises to a player: source (tuple of Player Decisions identifying what raised it), human-readable prompt, an ordered options tuple of Player Decisions (the implementation-provided order is part of the contract), and min/max counts. `min=0` marks a legally declinable query.

_Avoid_: "Question" (working name), "prompt" alone (one field of a query)

**Player View**

What an Audited Test may see of a game: each player's zones and the stack, the objects in them by predefined class with where each is and whether it is tapped, life totals, and the game's result (grilling 2026-10-05).
Everything else about an object — power, counters, keywords, effects — is judged only by what it causes in play.

_Avoid_: "board state" for the view (the board state is the whole game), "game state" as what tests read

**Priority Query**

The Player Query a player receives with priority, from fra-hard-v2 onward: the set of choices a real player could make at that moment — spells to cast, lands to play, abilities to activate — where declining passes priority (ADR-017).
One action may span several Player Queries within the same priority, such as choosing a card and then which of its faces to cast.

_Avoid_: "action query", "cast offer" (a Priority Query also offers abilities and passing), "directive" (the SOS and HOB-tier mechanism it replaces)

**Promoted Candidate** *(historical)*

A Benchmark Candidate checked into the bench repo's `candidates/<slug>--<hash8>/` by the promote script from the operator's private Config Repo: the worker-type definition with its base pinned by digest, the referenced knowledge and Agent Policy source trees vendored whole, the exported Candidate Bundle, and a README the operator completes (what the candidate varies). Vendor-at-promote is strict (#39 §4, the-ozolith ADR-0048): a referenced knowledge tree must exist and be declared publishable (a `PUBLISHABLE` marker at its root) or the candidate cannot be promoted and its results cannot be published. The Reference Candidates are the promoted candidates that vary nothing. Promotion and the `candidates/` tree were removed with Candidate Bundle execution.

_Avoid_: "imported candidate", "registered candidate" (nothing is registered — the directory is discovered)

**Published Result** *(historical)*

A Run Record (`manifest.json` + `scores.json`, byte for byte) ported from the private Results Repo into the bench repo's public `published/` tree by the publish script — as one transaction: all requested records appear or none — and committed by the operator — the commit is the approval stamp. Publishable only when traceable: its candidate identity is a Promoted Candidate that verifies by recomputation (hard refusal otherwise). A record with `leaderboard_valid: false` may be published at the operator's discretion (warning, `--allow-invalid`) and can never enter a leaderboard, because tooling filters on the flag. Discovered by manifest, never by path convention; the organization of `published/` is manual. The publish path was removed with Candidate Bundle execution before any result was published.

_Avoid_: "leaderboard entry" (a leaderboard is a derivation over Published Results, future work), "exported result"

**Reference Candidate** *(historical)*

One of the public vanilla candidates checked in under `candidates/` (#65): `vanilla-claude` and `vanilla-codex` — the stock TheOzolith run image for the adapter, no setup, no knowledge, no Agent Policy, the adapter's default model spelled as its most-pinned provider ID, the model's default effort. They vary nothing: the fixed points every operator can run (smoke, calibration, Pipeline Validation Runs) and compare against. Pi joins when its adapter exists.

_Avoid_: "baseline agent", "default candidate"

**Reference Tests**

The agent-visible, editable, never-graded tests staged in a Workspace: FDN Reference Tests and Engine Reference Tests (grilling 2026-10-02).
They may be wrong, including by encoding a Known Defect; a good agent fixes a test that contradicts `RULEBOOK.txt`.

_Avoid_: "visible tests" (informal), "staged tests" (informal)

**Replay Validation**

Engine correctness check that replays 17lands GRE (Game Rules Engine) state streams through the Python engine and verifies full game state at every GRE message boundary. Data source: 17lands pre-parsed GRE JSON — clean JSON files containing `GameStateType_Full` and `GameStateType_Diff` messages with object-level fidelity (zones, gameObjects by `grpId`/`instanceId`, life totals, annotations). Execution model: **observer mode** with state-diff comparison — seat 1 (17lands user) fully validated, seat 2 (opponent) actions oracle-injected from public game objects. Single parser, single format. See [17lands Replay Data Schema](docs/specs/17LANDS-REPLAY-SCHEMA.md) and [ADR-003](docs/adr/ADR-003-replay-validation-over-differential-testing.md).

_Avoid_: "differential testing" (deprecated XMage approach), "checkpoint validation" (we do full state comparison, not just EOT checkpoints), "aggregate CSV" (that's a different 17lands dataset)

**Results Repo**

The dedicated private git repository that is the home of benchmark results (#39 §3), git-as-truth: `results/<candidate-hash>/<run-id>/` holding one Run Record each, `results/<candidate-hash>/candidate/` holding the vendored Candidate Bundle of an `ozolith-v1` candidate (written once on its first run, verified at write time — the copy must recompute to the directory's Candidate Hash — immutable; #65), a derived `runs.jsonl` index regenerated from the tree (never hand-edited, never authoritative), and a root `AGENTS.md` carrying the full schema so the repo is self-contained for analysis agents. Heavy artifacts (transcripts, snapshots, per-card trees) never enter it — records carry pointers — except each record's Workspace Archive; Exclusions live beside the records. Written only through `silverquillm.results_repo`; laid out by `silverquillm results-init <clone>`; the legacy Validated Results corpus is backfilled into it by `scripts/migrate_validated_results.py`.

_Avoid_: "results dir" (the per-run `docker/<image>/results/` working output), "leaderboard repo" (publishing is the separate port into the bench repo's `published/` — see Published Result)

**Resume Chain**

Sequence of Benchmark Runs linked via `resumed_from`, where each run after the first stages from the prior run's `workspace_final/`. Each leg is an independent Benchmark Run with its own `run_name`, results directory, Hard Timeout, snapshots, and evaluation. The chain is an audit-trail concept; the runner does not aggregate results across legs. CLI: `silverquillm resume <prior-run-id>`. See ADR-008.

_Avoid_: "session" (deprecated — too vague; use Resume Chain + Resume Leg), "continuation run"

**Resume Leg**

A Benchmark Run with `resumed_from` set — any run in a Resume Chain other than the first. Resume Legs are independent Benchmark Runs in every other respect (own results dir, own snapshots, own evaluation, own `run_summary.json`). Resume Legs are never leaderboard-valid: any run with `resumed_from` set has `leaderboard_valid = false` — they inherit prior-leg workspace state, so they are not head-to-head comparable with fresh full-set runs.

_Avoid_: "resumed session", "continuation run"

**Resume Preamble**

Extra lines the runner appends to the User Prompt when staging a Resume Leg. Always informs the agent (a) that this is a resume of `<prior-run-id>`, (b) that prior tests/implementations may already exist, and (c) that the workspace `.git` records prior commits. Conditional additional lines disclose (i) prior-run snapshot-fallback rollback when applicable, and (ii) image change when `--image` differs from the prior run's image. Image-agnostic — agents with no internal coordinator/cycle structure benefit equally.

_Avoid_: "resume notice", "resume header"

**Run Manifest** *(historical image runs)*

Minimal runtime facts written by the runner to `/workspace/run_manifest.json` immediately before container launch. Contains only `timeout_seconds` and `deadline_utc`; it is advisory to the Agent Container and does not configure agent behavior.

_Avoid_: "config.json" (implies agent configuration), "agent config"

**Run Record**

An immutable account of a Benchmark Run's selected candidate, benchmark, conditions, observed outcomes, and available evidence.
It retains grading, Estimated Cost, Agent Turns, and diagnostics when available, explaining missing or partial observations instead of discarding an unsuccessful run (grilling 2026-09-26).
Historical records retain their original schemas, identities, and interpretation.

_Avoid_: "run summary" (`run_summary.json` is the legacy per-run aggregate the record's scores are mapped from), "result" alone

**SOS Card Stub**

The starting-state `card_impl.py` for an SOS card: a `class CardName(CardImpl): pass` declaration with a TODO docstring. Pins class name, inheritance, and import path so audited tests can reliably import. Provides no behavior — `CardImpl` is no-op-by-default (all hooks return safe defaults), so stubs are runnable from day one and tests fail on missing behavior, not import/structure. The agent's task is to fill in the class body.

_Avoid_: "empty template" (technically inaccurate — stubs are non-empty), "skeleton card"

**Script Entry**

One step of a player's script in an Audited Test, from fra-hard-v2 onward: it answers that player's next action question — a Priority Query or a combat declaration — and every other question they receive until their following one, by preferences held as ordered branches, and states in plain terms the changes to the Player View it expects (grilling 2026-10-05).
A player's script is the only source of their answers.

_Avoid_: "directive" (the SOS channel), "Intent" (the HOB answering mechanism it replaces), "action" alone (an entry may only pass and answer choices)

**Seeded Defect**

A Known Defect introduced into a benchmark's baseline engine or FDN implementations on purpose (grilling 2026-10-02).
Seeded Defects are fixed per benchmark version, so every run on that version sees the same engine.

_Avoid_: "fuzzed engine", "fuzzing" (fuzzing names random-input testing), "planted bug"

**Simulated Benchmark**

A Platform Test that runs the whole run pipeline (staging, execution, grading, the Run Record) on a toy benchmark, with a stand-in for the agent's container and the Grader Container, so nothing launches a model or Docker (grilling 2026-10-03).
A Simulated Benchmark is an end-to-end test.

_Avoid_: "fake run", "mock benchmark" (only the agent host and the container runtime are stand-ins), "Pipeline Validation Run" (that runs a real benchmark through real containers)

**System Prompt**

Agent-optimization instructions baked into the Docker image's entrypoint. Controls how the agent executes (iteration strategy, mode-specific behavior, tool configuration). Not written by the runner. Contrast with User Prompt.

_Avoid_: "agent prompt" (ambiguous — could mean either prompt layer)

**Test Harvester** *(manual v1 / automated v2)*

The mechanism for improving audited tests from harvested run results. **Manual v1**: the on-demand harvest script + combined investigation/discovery skill in [AUDITED-TEST-IMPROVEMENT-WORKFLOW.md](docs/specs/AUDITED-TEST-IMPROVEMENT-WORKFLOW.md) — a human reviews suspect tests (ranked by cross-impl failure breadth) and promotion candidates. **Automated v2** *(future)*: a pass that harvests Validated Results and scores audited test quality (cross-impl breadth, discrimination, convention-coupling) to surface suspect tests and promotion candidates with less human triage. Replaces the retired self-eval / N×N cross-eval framing; not run after Release.

_Avoid_: "cross-eval" / "self-eval" (retired N×N framing), "cross-validation" (overloaded ML term)

**Test Interface**

The immutable, benchmark-owned interface through which Audited Tests build, play and observe a game from smoke and fra-hard-v2 onward: the `test_interface` module and the small engine surface it relies on, which a candidate's engine must keep (grilling 2026-10-05).
The candidate never changes it; grading pairs the benchmark's copy with the candidate's engine.
It succeeds the SOS-only Audited Test API.

_Avoid_: "test harness", "test_utils" (the Reference Tests' helper module), "Audited Test API" (the SOS predecessor)

**Test Oracle Impl**

A host-side implementation of a target card used as the behavioral reference for validating Audited Tests.
It belongs to the benchmark's Test Oracle Workspace and is never staged into candidate runs.

_Avoid_: "reference implementation" (already names FDN learning material at `workspace/cards/fdn/{cn}/card_impl.py`), "gold impl"

**Test Oracle Workspace**

A host-only mirror of a benchmark's agent-visible Workspace, holding its Test Oracle Impls and an independent engine.
It supports developing and validating Audited Tests while keeping oracle implementations separate from candidate runs.
Its engine may implement required mechanics independently; Audited Tests still use the canonical public API.

_Avoid_: "reference workspace" (reference is overloaded), "oracle" alone (ambiguous)

**Tested Mode**

Benchmark mode (`MODE=tested`) where the prompt instructs the agent to write tests and iterate. The agent self-manages iteration — no round limits enforced by the runner. Produces `card_impl.py` + `tests.py` per card. Compare against Blind Mode via separate runs.

_Avoid_: "test-informed implementation" (deprecated — was `tested_impl.py`)

**User Prompt**

Task-specific instruction written by the runner to `/workspace/prompt.md` at staging time. Describes what the agent should implement (e.g., "Implement all SOS cards in `/workspace/cards/sos/`"). It lists the benchmark's whole target-card problem set — a Benchmark Run always stages the entire set; card-subset ("workload") runs are retired. Contrast with System Prompt.

_Avoid_: "task prompt", "workspace prompt"

**Validated Results**

Per-run result artifacts committed under `docker/<image>/validated_results/<run-name>/`. Each run directory holds `eval_result.json` (aggregate pass/fail/total per card), a `cards/<card_id>/` subtree (`card_impl.py`, the exact `tests.py` used, and `result.json` with per-test failure node IDs and counts), plus logs, telemetry, `engine_diff.patch`, and manifests. The source corpus the harvest script reads. *Superseded as the results home by the Results Repo (#39 §3, #63)*: every run here is backfilled as a Run Record with a `legacy-tree` pointer back to this directory; the trees themselves are deleted by the retirement issue (#66), after which the pointers resolve only through git history.

_Avoid_: "results" alone (ambiguous with `results/{run_name}/` run output), "validated runs"

**Workload** *(retired — grilling 2026-08-27)*

Retired run-spec term. Formerly a card subset within a benchmark; killed because card subsets were a SOS-era hack that confuses benchmarks. One benchmark = one problem set; a run always consumes the whole set. The current run spec is candidate + benchmark + budget; historical runs also selected a mode. Cheap pipeline validation uses a dedicated smoke benchmark (its own small problem set of validated FDN cards), never a subset of a real one.

_Avoid_: "workload", "card subset", "filtered run"

**Workspace**

The agent-writable run copy of `benchmarks/<benchmark>/workspace/`, containing the engine, FDN reference cards, target-card stubs, test scaffolding, and agent-facing documentation.
Karn runs seed Git history from a trusted benchmark baseline and receive task input through declared file mounts under the [Karn Benchmark Contract](docs/specs/KARN-BENCHMARK-CONTRACT.md#independent-execution).
Historical image runs wrote `prompt.md` and `run_manifest.json` into the Workspace and preserved the previous run's `.git` when resuming.

_Avoid_: "working directory", "sandbox", "per-card workspace" (deprecated — workspace is per-run), "staged from scratch" (deprecated — workspace is a pre-built directory copied wholesale)

**Workspace Archive**

The graded Workspace copy of a Run Record, kept in the Results Repo as a diff from its benchmark input's staged baseline, so any host can rebuild and re-grade it.

_Avoid_: "workspace snapshot" (an Output Snapshot taken during the run), "workspace backup"

**Writable Engine**

The engine source in the Workspace that the agent may modify throughout a Benchmark Run.
Karn retains and grades the engine from the selected final or fallback Workspace under the [Karn Benchmark Contract](docs/specs/KARN-BENCHMARK-CONTRACT.md#operator-entrypoints-and-records).
Historical image runs also recorded differences from the host baseline as `engine_diff.patch`.

_Avoid_: "persistent engine" (deprecated — implied per-card sequential accumulation), "shared engine"

## Relationships

- A Benchmark Run evaluates one Benchmark Candidate against the selected benchmark's configured Card Pool and instruction data.
- A Benchmark Run launches one container session. The agent receives the benchmark's entire problem set (every target card) in a single Workspace — one benchmark = one problem set; there is no card-subset "workload" notion (grilling 2026-08-27).
- FDN cards are in-context examples (filled `card_impl.py` + colocated `tests.py` demonstrating the testing pattern). SOS cards are benchmark targets (SOS Card Stubs to fill in).
- Each agent produces `card_impl.py` per SOS card. In Tested Mode, also `tests.py` per card.
- The agent has a Writable Engine (`/workspace/engine/`) and may extend it freely throughout the run.
- All evaluation is post-run. After the container exits, the evaluator runs tests against harvested implementations and the final engine state.
- FDN Card Regression: evaluator runs `tests/audited/fdn/` against pre-filled FDN card impls + agent's final Writable Engine. Detects broken card behavior.
- Engine Regression: evaluator runs the Audited Engine Tests against agent's final Writable Engine. Detects broken rules mechanics.
- Self-eval / N×N cross-eval are retired; the Test Harvester (manual v1, automated v2) improves audited tests instead. Automated v2 test-quality scoring is future work.
- The Base Set forms the reference codebase agents can browse. No Expanded Pool — agents implement new mechanics from scratch.
- A Draft Set may span multiple Scryfall set codes (e.g., FDN + SPG).
- Draft Set defines the card pool for Replay Validation (17lands replays are draft games).
- All card tests follow a uniform structure: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. FDN and SOS tests share this structure.
- The Base Set's Draft Set cards (FDN 001–291 + SPG 074–083) are validated via Replay Validation against 17lands GRE JSON data before scored benchmark runs.
- A Pipeline Validation Run exercises the orchestration pipeline; its observations are retained as learning data alongside other run outcomes.
- The existing publication pipeline requires a Promoted Candidate that verifies by recomputation and permits its knowledge to be published; these publication rules do not gate collection or analysis of Karn run data.
- Each Login Profile has one Estimated Weekly Usage, fed by every Benchmark Run that used it, excluded runs included.
- A Batch holds ordered run specs; the scheduler executes one run at a time, resolves each candidate's identity at run start, and records outcomes in its own state, never in the Batch.
- Filesystem checks (does the file exist, does it differ from the template?) are the source of truth for agent output. Exit codes, stdout, and thinking traces are diagnostics only.
- `run_summary.json` is automatically generated after evaluation by aggregating per-card `result.json` files. The aggregator is a pure, idempotent function.
- The runner does NOT orchestrate test iteration — the agent self-manages. The runner stages, launches, harvests, evaluates.
- On container timeout, the runner harvests partial results. Completed cards are evaluated normally; unfinished cards scored as zero.
- Historical **Blind** and **Tested** modes varied test instructions. New Karn runs take their guidance from the selected benchmark and have no independent mode selector.
- Audited Tests are evaluation-only artifacts — never staged in the agent's workspace, never in results directories. Reference Tests are the agent-visible, editable, ungraded counterpart: FDN Reference Tests at `workspace/cards/fdn/{collector_number}/tests.py` and Engine Reference Tests at `workspace/engine_tests/` (ADR-006). Audited target-card tests live host-side only — there is no `workspace/tests/cards/` directory.
- hob-medium and SOS predate the Audited Engine Tests suite and grade Engine Regression from the host copy of their Engine Reference Tests; both are frozen (grilling 2026-10-02).
- The runner is the hard timeout authority. Historical Agent Containers may read the Run Manifest for pacing, but correctness does not depend on honoring it.
- Output Snapshots are runner-owned, Workspace-only, and independent of candidate cooperation. The runner may use a prior snapshot as fallback if the final engine state is unusable.
- Historical image runs write the User Prompt to `/workspace/prompt.md`; Karn task input follows the Construct Definition's declared file mounts.
- Hard Timeout and Hang Timeout are independent — either can trigger `docker stop -t 10` to end a benchmark run.
- A Test Oracle Workspace has an engine independent of the corresponding benchmark's agent-visible baseline; mechanics needed by an oracle do not alter that baseline merely for oracle convenience.
- Audited tests call only public APIs present in the canonical engine. Tests never depend on extensions present in the Test Oracle Workspace's engine but absent from canonical — otherwise correct agent impls using different primitives would fail tests for non-correctness reasons.
- Audited Tests are developed and validated against the matching Test Oracle Impl, then promoted to the benchmark's host-side authoritative audited-test tree; benchmark identity and target set code are resolved separately.
- Audited tests target observable game-state outcomes ("what the card does"), not card-text annotations ("what the card says"). Ability Words are not tested for presence; only the behavior described by the text following the ability word is asserted.
- The Audited Test API is the only sanctioned way an audited test touches the engine. It references only canonical-engine primitives and composes or duplicates canonical behavior (e.g. `cast_spell_from_exile` for alt-zone casts); building and using it requires no change to any workspace engine.
- The Host-Side Driver (`priority_loop`) advances audited tests by polling DeterministicPlayers for directives and resolving one stack object at a time; `advance_to_phase` fast-forwards turn structure (turn-based actions, triggers, end-of-turn cleanup) without opening priority windows, though a triggered ability that forces a choice is still answered from the choice script.
- Audited tests import whatever engine they run on (`engine.*` — the oracle during validation, the candidate during evaluation); portability comes from every candidate implementing the canonical public API, not from restricting imports. The paradigm forbids private-attribute poking (`_script`, `_resolve_targets`), not engine imports.
- Mechanics absent from the canonical engine (sos_57 `mana_spent` refund, sos_226 casualty, sos_201 miracle, sos_245 affinity, sos_1 / sos_120 graveyard→exile redirect, sos_97 coin-flip RNG) are exercised indirectly through canonical entrypoints + observable-state assertions, with RNG made deterministic test-side via seed-replacement (`game.rng = random.Random(seed)`); no mechanic-specific test-API support and no engine change.
- Player-initiated casts/activations carry their targets on the directive; engine-initiated (triggered) objects take no directive and pull targets/choices from the choice script. `ActivateAbility` names the ability by its index into `get_activated_abilities()` / `get_loyalty_abilities()` (printed order).
