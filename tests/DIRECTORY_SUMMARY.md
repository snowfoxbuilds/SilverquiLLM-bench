# Directory Summary — `tests/`

## Purpose

Test root directory for the SilverquiLLM-bench project. Contains top-level test files, test utilities, and subdirectories for engine and card tests. Uses **pytest** as the test framework with ~1,400+ test functions total (expanded from ~1,119 in Phase 1 with benchmark module tests).

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `test_utils.py` | 474 | **Test helper API** — Convenience functions for tests: `create_game()` (wrapper with `DeterministicPlayer`), `set_board_state()` (direct zone/life/mana manipulation), `cast_spell()` (find-in-hand + cast + resolve), `advance_to_phase()` (safe fast-forward), `declare_attackers()` / `declare_blockers()` (name-based combat setup). `TestSetupError` exception. |
| `conftest.py` | 14 | **pytest config** — `pytest_collection_modifyitems` hook to filter out benchmark functions that get collected as tests. |
| `test_integration.py` | 775 | **End-to-end integration tests** — 9 tests exercising real engine APIs across multiple turns. |
| `test_scaffold.py` | 179 | **Project scaffold validation** — Verifies pyproject.toml metadata, directory structure, package importability, py.typed markers, ruff config. |
| `test_phase1_tech_debt.py` | 257 | **Phase 1 tech debt validation** — Python 3.12 target, removed backward-compat aliases, deprecation warnings in cleanup discard. |
| `test_benchmark_scaffold.py` | 175 | **Benchmark scaffold validation** — Verifies benchmark/ and benchmarks/ package structure, SOS data presence, pyproject config. |
| `test_card_classifier.py` | 410 | **Card classifier tests** — 24 tests covering tier classification, SOS integration, edge cases. |
| `test_card_spec.py` | 478 | **Card spec tests** — Spec generation, field validation, all-specs output. |
| `test_template_gen.py` | 378 | **Template generator tests** — 49 tests for class name conversion, base class resolution, template compilation/exec. |
| `test_docs_gen.py` | 235 | **Docs generator tests** — 76 tests for public class/enum/function extraction, token budget, module grouping. |
| `test_test_utils_doc.py` | 175 | **test_utils documentation tests** — Validates docs/test_utils.md content and accuracy. |
| `test_rules_skill.py` | 207 | **Rules indexer tests** — 18 tests for download, index, lookup, and rules_overview.md. |
| `test_cli_config.py` | 301 | **CLI + config tests** — Click CLI subcommands, YAML config loading and validation. |
| `test_prompts.py` | 222 | **Prompt template tests** — blind, test-informed, and iteration feedback prompt generation. |
| `test_agent_session.py` | 444 | **Agent session tests** — 43 tests for dataclass fields, workspace setup, OpenCode config, blind/test-informed phases. |
| `test_evaluator.py` | 424 | **Evaluator tests** — EvalResult dataclass, subprocess test execution, self/cross/audited eval. |
| `test_scorer.py` | 626 | **Scorer tests** — Score computation, 3-category metrics, leaderboard generation. |
| `test_results.py` | 656 | **Result recorder tests** — Run naming, directory init, card result saving, summary/aggregate output. |
| `test_prototype.py` | 511 | **Prototype selection tests** — Per-tier scoring, card selection, gap analysis. |
| `test_engine_extensions.py` | 422 | **Engine extension tests** — 21 tests for mana color tracking, colors_spent on cast, Converge mechanic. |
| `__init__.py` | — | Package init. |

## Subdirectories

- **`engine/`** — Unit tests for all engine modules (~850 tests). See `tests/engine/DIRECTORY_SUMMARY.md`.
- **`cards/`** — Unit tests for card implementations (~270 tests). See `tests/cards/DIRECTORY_SUMMARY.md`.

## Testing Approach

- **Deterministic**: All tests use `DeterministicPlayer` with scripted FIFO choices for full reproducibility.
- **Unit + Integration**: Each engine module has its own test file; integration tests validate cross-module interactions.
- **Benchmark tests**: Each `benchmark/` module has a corresponding `test_*.py` file at the tests root level.
- **Conventions**: Test classes named `Test<Feature>`, test methods `test_<behavior>`. Fixtures use `_make_game()`, `_make_player()` patterns.
- **conftest.py hook**: Filters out benchmark module functions (e.g., `test_informed_prompt`) that pytest would incorrectly collect as test functions.
