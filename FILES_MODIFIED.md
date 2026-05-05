# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Fix Phase 1 tech debt

### Implementation
- `pyproject.toml` — Set requires-python to >=3.12, mypy python_version to 3.12, removed tomli conditional dep
- `ruff.toml` — Set target-version to py312
- `cards/foundations/simple_spells.py` — Removed 7 backward-compat aliases (LightningBolt, LavaAxe, etc.)
- `engine/turn.py` — Added import warnings and warnings.warn() in cleanup discard fallback
- `KEY_DECISIONS.md` — Updated decision #2 to reflect Python 3.12 target
- `tests/test_scaffold.py` — Updated scaffold tests to expect 3.12/py312 instead of 3.10/py311

## Item 2: Benchmark package scaffold + SOS data fetch

### Tests
- (no test files provided by tester)

### Implementation
- `benchmark/__init__.py` — Created benchmark runner package with docstring
- `benchmarks/__init__.py` — Created benchmarks namespace package
- `benchmarks/sos/__init__.py` — Created SOS benchmark set package
- `benchmarks/sos/fetch_data.py` — SOS data fetcher with normalization, stats logging, and CLI
- `benchmarks/sos/data/sos.json` — Cached normalized SOS card data (368 cards from Scryfall)
- `benchmarks/sos/cards/.gitkeep` — Placeholder for SOS card implementations
- `benchmarks/sos/results/.gitkeep` — Placeholder for SOS benchmark results
- `pyproject.toml` — Added pyyaml and click deps; included benchmark* and benchmarks* in package discovery

## Item 3: Card complexity classifier

### Tests
- `tests/test_card_classifier.py` — 24 tests covering tier classification, SOS integration, edge cases

### Implementation
- `benchmark/card_classifier.py` — Heuristic-based card complexity classifier with targeting floor fix (target → at least medium)
- `benchmarks/sos/data/sos_classified.json` — Regenerated classification output for all 368 SOS cards with fixed targeting heuristic

## Item 4: Card spec generator

### Tests
- (no test files provided by tester)

### Implementation
- `benchmark/card_spec.py` — Card spec generator with generate_card_spec() and generate_all_specs() functions
- `benchmarks/sos/cards/*/card_spec.json` — Generated 368 per-card JSON spec files for SOS set

## Item 5: Template generator

### Tests
- `tests/test_template_gen.py` — 49 tests covering class name conversion, base class resolution, template compilation/exec

### Implementation
- `benchmark/template_gen.py` — Template generator with PascalCase word-boundary fix and ambiguous multi-type fallback to CardImpl

## Item 6: Engine API docs auto-generation

### Tests
- `tests/test_docs_gen.py` — 76 tests covering public classes, enums, functions, token budget, module grouping, output file

### Implementation
- `benchmark/docs_gen.py` — AST-based engine API doc generator; removed hard-coded incorrect examples block
- `docs/engine_api.md` — Regenerated accurate engine API reference from AST-only extraction


## Item 7: test_utils documentation for agents

### Implementation
- `docs/test_utils.md` — API reference for test helpers: create_game, set_board_state, cast_spell, advance_to_phase, declare_attackers, declare_blockers

## Item 8: MTG rules indexer + rules_overview.md

### Tests
- `tests/test_rules_skill.py` — 18 tests covering download, index, lookup, and rules_overview.md

### Implementation
- `benchmark/rules_skill.py` — MTG comprehensive rules downloader (with force param), parser, indexer, lookup, and generate_rules_overview() function
- `benchmarks/sos/data/rules_overview.md` — Hand-crafted compact MTG rules overview (~573 tokens)
- `benchmarks/sos/data/comprehensive_rules.txt` — Cached comprehensive rules (stub fallback)

## Item 9: Runner CLI scaffold + YAML config

### Implementation
- `benchmark/config.py` — BenchmarkConfig dataclass and load_config() with YAML validation
- `benchmark/cli.py` — Click CLI with run/eval/score/cards subcommands
- `config.example.yaml` — Example YAML configuration file
- `pyproject.toml` — Added [project.scripts] benchmark entry point

## Item 10: Prompt templates module

### Tests
- `tests/test_prompts.py` — Tests for prompt template functions (blind, test-informed, iteration feedback)

### Implementation
- `benchmark/prompts.py` — Parameterized prompt templates using str.format_map; imports card_name_to_class_name from template_gen for consistent class name derivation
- `tests/conftest.py` — pytest_collection_modifyitems hook to filter out benchmark functions collected as tests

## Item 11: Agent session manager

### Tests
- `tests/test_agent_session.py` — 43 tests covering dataclass fields, workspace setup, opencode config, blind/test-informed phases, cleanup

### Implementation
- `benchmark/agent_session.py` — AgentSession @dataclass with workspace setup, OpenCode config (exposing engine path), blind phase without template false-positive, test-informed with max_rounds_exhausted status, standalone convenience functions, and BlindResult/TestInformedResult dataclasses

## Item 12: Evaluation runner

### Implementation
- `benchmark/evaluator.py` — Evaluation runner with EvalResult dataclass, run_tests (subprocess pytest isolation), run_self_eval, run_cross_eval, run_audited_eval

## Item 13: Scoring calculator

### Implementation
- `benchmark/scorer.py` — Scoring calculator with Leaderboard dataclass, compute_scores (3-category metrics from EvalResults), generate_leaderboard (Markdown tables)

## Item 14: Result recording + output artifacts

### Implementation
- `benchmark/results.py` — Per-run result recording with generate_run_name, init_results_dir, save_card_result, save_run_summary, save_aggregates

## Item 15: Prototype card selection + engine gap analysis

### Tests
(no test files provided by tester)

### Implementation
- `benchmark/prototype.py` — Replaced binary prefer/fallback with per-tier scoring functions; added classified-data fallback for sos.json independence
- `benchmarks/sos/prototype_cards.json` — Re-selected 5 prototype cards with scoring-based preferences
- `benchmarks/sos/prototype_gaps.md` — Regenerated engine gap analysis (Converge mana tracking gap)

## Item 16: Minimal engine extensions for SOS prototype mechanics

### Tests
- `tests/test_engine_extensions.py` — 21 tests: mana color tracking, cast_spell colors_spent, prototype card instantiation, Converge mechanic

### Implementation
- `engine/mana.py` — Added `last_payment_colors` property and `_MANA_TO_COLOR` mapping for Converge mana color tracking
- `engine/casting.py` — Store `colors_spent` on card after mana payment in `cast_spell()`
- `tests/test_engine_extensions.py` — New test file for engine extension mechanics
