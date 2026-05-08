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
