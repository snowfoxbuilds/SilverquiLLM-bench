## Completed 2026-05-22

Phase 11: Runner Polish, Output Channels (8 items)

Branch: `execute-todo-with-subagents/runner-polish` → `main`

- [x] **Remove ****`--cards-dir`**** and ****`--engine-dir`**** CLI flags; hardcode repo-relative paths**
- [x] **Add ****`--cards`**** filter to ****`silverquillm run`**
- [x] **Write ****`run_manifest.json`**** during workspace staging**
- [x] **Update Docker entrypoints: remove ****`engine_work`**** copy, add file-based channel separation**
- [x] **Create ****`silverquillm/runner.py`**** with pipe-readers + poll-loop architecture**
- [x] **Integrate ****`ContainerLifecycle`**** into CLI ****`run`**** and ****`smoke`**** commands; update harvest and add ****`--hang-timeout`**
- [x] **Fix results directory structure: store under image directory, update run name format**
- [x] **Add pytest ****`integration`**** marker, ****`pytest-timeout`****, and alpine smoke pipeline test**
## Completed 2026-05-15

Phase 10: FDN Card Implementations (174 cards)

- [x] **Upgrade 4 simplified Aura implementations to full oracle text**
- [x] **Upgrade 3 simplified Planeswalker implementations to full oracle text**
- [x] **Upgrade 3 simplified Equipment/Creature implementations to full oracle text**
- [x] **Implement White new cards — batch 1 (10 creatures)**
- [x] **Implement White new cards — batch 2 (10 creatures + spells)**
- [x] **Implement Blue new cards — batch 1 (10 creatures)**
- [x] **Implement Blue new cards — batch 2 (10 creatures + spells)**
- [x] **Implement Black new cards (19 cards)**
- [x] **Implement Red new cards (15 cards)**
- [x] **Implement Green new cards (14 cards)**
- [x] **Implement Multicolor new cards (11 cards)**
- [x] **Implement White + Blue reprints (18 cards)**
- [x] **Implement Black + Red reprints (21 cards)**
- [x] **Implement Green + Multicolor reprints (24 cards)**
- [x] **Implement Artifact reprints + Secluded Courtyard (9 cards)**
## Completed 2026-05-13

Phase 9: Docker Container Flow + FDN Card Restructure (PR #12 — 12 items)

Branch: `execute-todo-with-subagents/phase9-docker-container-flow-20260513-082836` → `main`

Status: PR open, review requested changes (README/PROJECT_MAP not updated, old files not confirmed deleted, FDN shims need tracking)

- [ ] Delete remaining old harness code from `silverquillm/`
- [ ] Restructure FDN cards to per-collector-number layout
- [ ] Restructure SOS cards to unified `cards/` layout
- [ ] Rewrite `silverquillm/card_loader.py` for unified card layout
- [ ] Implement `silverquillm/workspace.py` — workspace staging
- [ ] Create Docker images: `docker/opencode-tested/` and `docker/opencode-blind/`
- [ ] Implement `silverquillm/cli.py` — `run` and `smoke` commands
- [ ] Rewrite `silverquillm/evaluator.py` — 3 evaluation dimensions
- [ ] Implement `silverquillm/results.py` — run summary generation
- [ ] Implement progress.jsonl protocol in entrypoints
- [ ] Update `pyproject.toml` and `README.md` for new architecture
- [ ] Clean up orphaned tests and verify full suite
## Completed 2026-05-12

Phase 7: Harness Architecture Refactor & Robustness (PR #11 — 16 items)

Branch: `execute-todo-with-subagents/harness-refactor-20260512-071236` → `main`

- [x] **Add ****`mode`**** to config and create ****`CardStrategy`**** ABC**
- [x] **Implement ****`BlindStrategy`**
- [x] **Implement ****`ImplTestStrategy`**
- [x] **Refactor ****`agent_session.py`****: remove harness-managed iteration**
- [x] **Decouple ****`harvest_results()`**** from violation status (fixes Issue #15)**
- [x] **Engine snapshot and rollback on timeout**
- [x] **Enforce ****`timeout_per_card`**** (fixes Issue #14)**
- [x] **Move all evaluation to post-run**
- [x] **Refactor ****`EvalResult`**** and ****`result.json`**** to v2 schema**
- [x] **Automatic ****`run_summary.json`**** aggregation**
- [x] **Allowlist-based contamination checker**
- [x] **Fix ****`test_utils.md`**** import path (fixes Issue #11)**
- [x] **Add ****`GameState`**** to template imports (fixes Issue #12)**
- [x] **Simplify postmortem schema**
- [x] **Pre-flight validation at run start**
- [x] **Smoke tests with mock adapter (****`tests/test_harness.py`****)**
## Completed 2026-04-28

Phase 1: Engine & Base Set (PR #1 — 24 items, 1,254 tests, 74 files)

Branch: `execute-todo-with-subagents/phase1-engine` → `main`

- [x] **Project scaffold: pyproject.toml, package layout, dev tooling**
- [x] **Core enums and type definitions**
- [x] **Zone containers**
- [x] **Player ABC and DeterministicPlayer**
- [x] **Mana pool and cost payment**
- [x] **GameState scaffold and turn structure**
- [x] **The Stack: data structure, priority passing, and resolution**
- [x] **State-based actions**
- [x] **Card base classes and CardImpl interface**
- [x] **Casting and resolution pipeline**
- [x] **Triggered abilities system**
- [x] **Activated abilities system**
- [x] **Combat system**
- [x] **Continuous effects and layer system**
- [x] **Replacement effects engine**
- [x] **Game setup, helper actions, and the full game loop**
- [x] **test_utils module for engine validation**
- [x] **Card registry and Scryfall data pipeline**
- [x] **Basic land implementations (Plains, Island, Swamp, Mountain, Forest)**
- [x] **Vanilla and French vanilla creatures from Foundations (~15 cards)**
- [x] **Simple instants and sorceries from Foundations (~10 cards)**
- [x] **Simple enchantments and artifacts from Foundations (~5 cards)**
- [x] **End-of-turn cleanup and damage clearing**
- [x] **Integration test: multi-turn game with Foundations cards**
## Completed 2026-05-05

Phase 2: Benchmark Harness & Prototype (PR #2 — 16 items)

Branch: `execute-todo-with-subagents/phase2-harness` → `main`

- [x] **Fix Phase 1 tech debt** (Python 3.12 alignment, remove aliases, cleanup warning)
- [x] **Benchmark package scaffold + SOS data fetch** (368 cards from Scryfall)
- [x] **Card complexity classifier** (5-tier heuristics)
- [x] **Card spec generator** (per-card JSON specs)
- [x] **Template generator** (Python skeleton templates)
- [x] **Engine API docs auto-generation** (AST-based)
- [x] **test_utils documentation for agents**
- [x] **MTG rules indexer + rules_**[**overview.md**](http://overview.md/)
- [x] **Runner CLI scaffold + YAML config** (click-based)
- [x] **Prompt templates module**
- [x] **Agent session manager** (workspace setup, OpenCode integration, contamination controls)
- [x] **Evaluation runner** (subprocess-isolated pytest, self/cross/audited eval)
- [x] **Scoring calculator** (3-category metrics, weighted scores, leaderboard)
- [x] **Result recording + output artifacts** (per-run directory structure)
- [x] **Prototype card selection + engine gap analysis**
- [x] **Minimal engine extensions for SOS prototype mechanics** (Converge mana color tracking)
## Completed 2026-05-09

Phase 4: Complete the Base Set — FDN 001–291 (PR #6 — 15 items, ~191 cards, 3,786 tests)

Branch: `execute-todo-with-subagents/phase4-base-set` → `main`

- [x] **Fix ****`is_aura`**** default ****`True`**** → ****`False`**
- [x] **Wire SBA trigger queueing**
- [x] **Centralize zone-transition hooks into ****`move_to_zone()`**
- [x] **Batch 1: Remaining vanilla & French vanilla creatures (7 cards)**
- [x] **Batch 2: Simple non-targeted instants & sorceries (15 cards)**
- [x] **Batch 3: Simple targeted instants & sorceries (18 cards)**
- [x] **Batch 4: Non-basic lands (13 cards)**
- [x] **Batch 5: Creatures with ETB triggers (29 cards)**
- [x] **Batch 6: Auras (10 cards)**
- [x] **Batch 7: Equipment (7 cards)**
- [x] **Batch 8: Creatures with death triggers (17 cards)**
- [x] **Batch 9: Creatures with activated abilities (19 cards)**
- [x] **Batch 10: Global enchantments (10 cards)**
- [x] **Batch 11: Remaining artifacts & planeswalkers (27 artifacts + 3 planeswalkers)**
- [x] **Batch 12: Modal spells, X-cost spells, kicker (16 cards)**
## Completed 2026-05-08

Phase 3: Multi-Agent Adapters, Postmortem & Spec Alignment (PR #5 — 22 items)

Branch: `execute-todo-with-subagents/phase3-adapters` → `main`

- [x] **Rename ****`benchmark/`**** package to ****`silverquillm/`**
- [x] **Refactor ****`BenchmarkConfig`**** to use nested ****`agent:`**** block**
- [x] **Update all ****`BenchmarkConfig`**** consumers for nested agent config**
- [x] **Create ****`AgentAdapter`**** abstract base class**
- [x] **Implement ****`OpenCodeAdapter`**
- [x] **Implement ****`ClaudeCodeAdapter`**
- [x] **Implement ****`AiderAdapter`**
- [x] **Implement ****`PiAdapter`**
- [x] **Refactor ****`agent_session.py`**** to use ****`AgentAdapter`**
- [x] **Implement postmortem JSONL logging**
- [x] **Implement ****`agent_thoughts.md`**** narrative generation**
- [x] **Implement setup questions validation**
- [x] **Create ****`setup_questions.json`**** question bank**
- [x] **Audit and align tier key naming (****`tier`**** vs ****`complexity_tier`****)**
- [x] **Fix prompt templates: add explicit output filenames**
- [x] **Implement persistent engine per run**
- [x] **Implement regression test runner**
- [x] **Sort cards by complexity tier for sequential processing**
- [x] **Capture engine diffs as per-card artifacts**
- [x] **Update prompts to inform agents about engine extensibility**
- [x] **Add Category 4 scoring: Engine Extension Quality**
- [x] **Expand Foundations card pool (batch 1: +30 cards)**
## Completed 2026-05-10

Phase 5: Replay Validation Pipeline (PR #7 — 11 items, 10 SPG cards, replay parser + validator)

Branch: `execute-todo-with-subagents/phase5-replay-validation` → `main`

- [x] **Hybrid mana parsing and cost payment**
- [x] **Cost reduction during casting**
- [x] **Protection from qualities (keyword ability)**
- [x] **Extra turns infrastructure (stub)**
- [x] **SPG Batch 1: Simple spells and utility creatures (5 cards)** — Condemn, Grim Tutor, Goblin Bushwhacker, Paradise Druid, Bloom Tender
- [x] **SPG Batch 2: Complex permanents and spells (5 cards)** — Sphinx's Tutelage, Embercleave, Akroma's Memorial, Temporal Manipulation, Fiend Artisan
- [x] **Card ID mapping (grpId → card name)**
- [x] **17lands GRE JSON parser**
- [x] **Replay executor (state-diff observer mode)**
- [x] **Divergence detection and reporting**
- [x] **CLI: ****`benchmark validate`**** command**
## Completed 2026-05-13

Phase 8 (partial): Fix PR #11 Regressions — 3 items completed before architecture pivot to Docker containers

- [x] **Fix ****`repo_root`**** contamination in ****`OpenCodeAdapter`**
- [x] **Fix ****`.pytest_cache`**** and other tool-cache false contamination**
- [x] **Fix preflight ****`_check_card_specs_dir()`**** flat glob**
Remaining Phase 8 items (standardize per-card paths, wire agent output, replace ThreadPoolExecutor, etc.) were obsoleted by the Docker container architecture pivot. Old adapter code deleted.

## Completed 2026-05-12

Phase 6: SOS Draft Set Completion & Audited Test Suites (PR #8 — 15 items, 647 audited test files)

Branch: `execute-todo-with-subagents/phase6-audited-tests` → `main`

- [x] **Include Mystical Archives (SOA set, cn 1–65)**
- [x] **Include Special Guests (SPG set, cn 149–158)**
- [x] **Enforce SOS base set draft cutoff at collector number 271**
- [x] **Re-run classification and spec generation on updated card pool**
- [x] **Create per-card audited test directory structure and **[**conftest.py**](http://conftest.py/)
- [x] **Generate SOS stub card classes from card specs**
- [x] **FDN audited tests: Batch 1 — Basic lands and vanilla/French vanilla creatures (~30 cards)**
- [x] **FDN audited tests: Batch 2 — Simple instants and sorceries (~60 cards)**
- [x] **FDN audited tests: Batch 3 — Creatures with triggers and activated abilities (~65 cards)**
- [x] **FDN audited tests: Batch 4 — Enchantments, equipment, artifacts, and planeswalkers (~70 cards)**
- [x] **FDN audited tests: Batch 5 — Non-basic lands, SPG cards, and remaining cards (~76 cards)**
- [x] **SOS audited tests: Batch 1 — Trivial and simple complexity cards**
- [x] **SOS audited tests: Batch 2 — Moderate complexity cards**
- [x] **SOS audited tests: Batch 3 — Complex and extreme complexity cards**
- [x] **Wire per-card audited tests into the evaluation pipeline**
## Completed 2026-05-07

Phase 2.5: CLI Wiring, Contamination Controls & Integration Test (PR #3 — 11 items)

Branch: `execute-todo-with-subagents/phase-2-5-cli-wiring` → `main`

- [x] **Expand ****`_check_violations`**** to cover all protected directories and return structured violations**
- [x] **Wire enhanced violation checks into both agent run methods**
- [x] **Add card-spec loading and filtering utility**
- [x] **Add ****`--cards`****, ****`--prototype`****, and ****`--dry-run`**** flags to ****`benchmark run`**
- [x] **Wire ****`benchmark run`**** orchestration loop**
- [x] **Wire ****`benchmark run`**** post-loop: self-eval and summary**
- [x] **Wire ****`benchmark eval`**** command**
- [x] **Wire ****`benchmark score`**** command**
- [x] **Create integration test helpers: mock OpenCode and test fixtures**
- [x] **Full pipeline integration test with Eager Glyphmage and Ajani's Response**
