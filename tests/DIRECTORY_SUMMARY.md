# Directory Summary — `tests/`

## Purpose

Test root directory for the SilverquiLLM-bench project. Contains top-level test files, test utilities, and subdirectories for engine, card, benchmark integration, and per-card audited tests. Uses **pytest** as the test framework with ~3,500+ test functions total across 100+ test files, plus hundreds of per-card audited test files under `audited/`.

## Key Files

| File | Responsibility |
|------|---------------|
| `conftest.py` | **pytest config** — `pytest_collection_modifyitems` hook to filter out benchmark functions that get collected as tests; registers `integration` marker. |
| `test_utils.py` | **Test helper API** — `create_game()`, `set_board_state()`, `cast_spell()`, `advance_to_phase()`, `declare_attackers()`, `declare_blockers()`. `TestSetupError` exception. |
| `test_integration.py` | **End-to-end integration tests** — Multi-turn game scenarios. |
| `test_scaffold.py` | **Project scaffold validation** — pyproject.toml, directory structure, package importability. |
| `test_benchmark_scaffold.py` | **Benchmark scaffold validation** — Verifies silverquillm/ and benchmarks/ package structure. |
| `test_package_rename.py` | **Package rename validation** — Confirms `benchmark/` → `silverquillm/` rename. |
| `test_adapter_base.py` | **Adapter base tests** — AgentAdapter ABC, registry, factory, retry logic. |
| `test_opencode_adapter.py` | **OpenCode adapter tests** — Subprocess behavior, stdin passing. |
| `test_claude_code_adapter.py` | **Claude Code adapter tests** — CLI wrapping, --print flag. |
| `test_aider_adapter.py` | **Aider adapter tests** — --message-file, --no-auto-commits. |
| `test_pi_adapter.py` | **Pi adapter tests** — --no-interactive, stdin passing. |
| `test_agent_session.py` | **Agent session tests** — Workspace setup, blind/test-informed phases, adapter lifecycle. |
| `test_agent_session_adapter.py` | **Session + adapter integration** — Adapter wiring into session. |
| `test_agent_session_refactor.py` | **Agent session refactor tests** — Refactored session behavior validation. |
| `test_agent_config.py` | **Agent config tests** — Nested AgentConfig dataclass. |
| `test_agent_thoughts.py` | **Agent thoughts tests** — Narrative generation from postmortem JSONL. |
| `test_postmortem_logging.py` | **Postmortem logging tests** — JSONL append, timing, error handling. |
| `test_postmortem_schema_v2.py` | **Postmortem schema v2 tests** — 26 tests for structured event helpers (`_append_file_written`, `_append_eval_result`, `_append_regression_check`) and raw log schema. |
| `test_config_consumers.py` | **Config consumer tests** — All modules correctly use nested config. |
| `test_card_classifier.py` | **Card classifier tests** — Tier classification, SOS integration. |
| `test_card_spec.py` | **Card spec tests** — Spec generation, field validation. |
| `test_card_loader.py` | **Card loader tests** — Spec loading, filtering. |
| `test_card_sorting.py` | **Card sorting tests** — Complexity tier sorting. |
| `test_template_gen.py` | **Template generator tests** — Class name conversion, template compilation. |
| `test_docs_gen.py` | **Docs generator tests** — AST extraction, token budget. |
| `test_rules_skill.py` | **Rules indexer tests** — Download, index, lookup. |
| `test_prompts.py` | **Prompt template tests** — All prompt types. |
| `test_engine_extensibility_prompts.py` | **Engine extensibility prompt tests** — Extensibility instructions in prompts. |
| `test_evaluator.py` | **Evaluator tests** — Subprocess test execution, eval scenarios. |
| `test_eval_result_v2.py` | **EvalResultV2 tests** — Mode-aware v2 eval schema, v1→v2 normalization, result persistence. |
| `test_scorer.py` | **Scorer tests** — 4-category metrics, leaderboard generation. |
| `test_cat4_scoring.py` | **Category 4 scoring tests** — Engine extension quality scoring. |
| `test_results.py` | **Result recorder tests** — Run naming, directory init, artifacts. |
| `test_regression.py` | **Regression runner tests** — Cross-card validation, feedback prompts. |
| `test_regression_runner.py` | **Regression runner integration** — End-to-end regression flows. |
| `test_persistent_engine.py` | **Persistent engine tests** — Engine lifecycle, diffs, commits. |
| `test_engine_diff.py` | **Engine diff tests** — Diff computation. |
| `test_prototype.py` | **Prototype selection tests** — Per-tier scoring, gap analysis. |
| `test_tier_naming.py` | **Tier naming tests** — `tier` / `complexity_tier` key alignment. |
| `test_prompt_filenames.py` | **Prompt filename tests** — Output filename instructions in prompts. |
| `test_setup_questions.py` | **Setup questions tests** — Validation logic. |
| `test_setup_questions_bank.py` | **Setup questions bank tests** — Question bank structure, topic coverage. |
| `test_cli_config.py` | **CLI + config tests** — Click subcommands, YAML loading. |
| `test_cli_run_flags.py` | **CLI run flag tests** — --dry-run, --cards, --prototype. |
| `test_cli_orchestration.py` | **CLI orchestration tests** — Run loop, result saving. |
| `test_cli_eval.py` | **CLI eval tests** — `benchmark eval` subcommand. |
| `test_cli_score.py` | **CLI score tests** — `benchmark score` subcommand. |
| `test_post_loop_eval.py` | **Post-loop eval tests** — `run_self_eval_flat`. |
| `test_sos_base_cutoff.py` | **SOS base cutoff tests** — 13 tests for SOS base cutoff at cn 271, cache freshness, total count 346. |
| `test_sos_stubs.py` | **SOS stub tests** — 346-card registration, attribute derivation, colors, no auto-load, deterministic generation, conftest integration. |
| `test_sos_regenerated_artifacts.py` | **SOS artifact regeneration tests** — 26 tests for 346-card pool integrity, classification, specs, docs. |
| `test_audited_per_card.py` | **Audited per-card test runner** — Parametrized per-card test discovery and execution. |
| `test_violation_wiring.py` | **Violation wiring tests** — Violation checks in agent runs. |
| `test_timeout_enforcement.py` | **Timeout enforcement tests** — 35 tests for hard timeout at strategy and adapter level with kill(). |
| `test_card_id_map.py` | **Card ID map tests** — card ID map JSON structure and build script tests. |
| `test_no_stale_iterations.py` | **Stale iterations tests** — verifies no stale iterations references leak into serialized results. |
| `test_signal_handler.py` | **Signal handler tests** — signal handler registration, restoration, and interrupt behavior. |
| `test_post_eval.py` | **Post-eval tests** — CardEvalResult dataclass, run_post_eval flow, self-eval, audited eval, result.json persistence, CLI integration. |
| `test_aggregator.py` | **Aggregator tests** — aggregate_run() pure function, RunSummary dataclass, persistence, idempotency. |
| `test_allowlist_contamination.py` | **Allowlist contamination tests** — 23 tests for allowlist-based contamination detection. |
| `test_preflight.py` | **Preflight tests** — 27 tests for pre-flight validation (card_specs_dir, config, workspace, template imports, test_utils, happy path, error aggregation, workspace isolation). |
| `test_harness.py` | **Harness smoke tests** — 39 deterministic end-to-end tests covering full harness pipeline with MockAdapter. |
| `test_strategies.py` | **Strategy tests** — BlindStrategy and ImplTestStrategy behavior. |
| `test_replay_parser.py` | **Replay parser tests** — 39 tests for GRE JSON parsing: game setup, opening hands, state reconstruction, land plays, life totals, draws, ObjectIdChanged tracking. |
| `test_replay_executor.py` | **Replay executor tests** — 23 tests for ReplayExecutor initialization, step execution, state comparison, seat 1/2 behavior. |
| `test_divergence_detection.py` | **Divergence detection tests** — 43 tests for DivergenceType, Divergence, ValidationReport, ValidatingExecutor, validate_replay. |
| `test_integration_helpers.py` | **Integration helpers tests** — run_utils, result conversion. |
| `test_engine_extensions.py` | **Engine extension tests** — Converge mana tracking. |
| `test_phase1_tech_debt.py` | **Tech debt validation** — Python 3.12, removed aliases. |
| `test_test_utils_doc.py` | **test_utils doc tests** — docs/test_utils.md accuracy. |

## Subdirectories

- **`engine/`** — Unit tests for all engine modules. See `tests/engine/DIRECTORY_SUMMARY.md`.
- **`cards/`** — Unit tests for card implementations (25 test files). See `tests/cards/DIRECTORY_SUMMARY.md`.
- **`benchmark/`** — Integration tests and helpers. See `tests/benchmark/DIRECTORY_SUMMARY.md`.
- **`audited/`** — Per-card audited test directories. Contains `fdn/` (260+ FDN card test dirs) and `sos/` (346 SOS Draft Set card test dirs with SOA/SPG subsets). Each card has a numbered directory with `tests.py`. Conftest files inject `card_impl` fixtures via `CardRegistry` class-name mapping.

## Testing Approach

- **Deterministic**: All tests use `DeterministicPlayer` with scripted FIFO choices.
- **Unit + Integration**: Each module has its own test file; integration tests validate cross-module interactions.
- **Conventions**: Test classes `Test<Feature>`, test methods `test_<behavior>`. Fixtures use `_make_game()`, `_make_player()` patterns.
- **conftest.py hook**: Filters out benchmark functions that pytest would incorrectly collect as tests.
