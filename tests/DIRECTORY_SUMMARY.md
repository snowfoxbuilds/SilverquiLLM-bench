# Directory Summary — `tests/`

## Purpose

Test root directory for the SilverquiLLM-bench project. Contains top-level test files, test utilities, and subdirectories for engine, card, benchmark integration, and per-card audited tests. Uses **pytest** as the test framework with ~3,500+ test functions total across 100+ test files, plus hundreds of per-card audited test files under `audited/`.

## Key Files

| File | Responsibility |
|------|---------------|
| `conftest.py` | **pytest config** — `pytest_collection_modifyitems` hook to filter out benchmark functions that get collected as tests; registers `integration` marker for tests requiring Docker/network (skipped by default). |
| `test_utils.py` | **Test helper API** — `create_game()`, `set_board_state()`, `cast_spell()`, `advance_to_phase()`, `declare_attackers()`, `declare_blockers()`. `TestSetupError` exception. |
| `test_integration.py` | **End-to-end integration tests** — Multi-turn game scenarios. |
| `test_scaffold.py` | **Project scaffold validation** — pyproject.toml, directory structure, package importability. |
| `test_benchmark_scaffold.py` | **Benchmark scaffold validation** — Verifies silverquillm/ and benchmarks/ package structure; asserts legacy `benchmarks/sos/results/` directory is removed. |
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
| `test_tests_hash.py` | **tests_hash field tests** — 13 tests verifying SHA-256 correctness of `CardResult.tests_hash`: hash match, determinism, change-on-edit, missing-file edge case (empty string), and additive-only preservation of existing `CardResult` fields. |
| `test_test_nodes.py` | **test_nodes field tests** — 29 tests verifying per-node pass/fail capture (real pytest runs), nodeid normalization, count consistency with `tests_passed`/`tests_failed`, collection/setup error handling, JSON persistence round-trip of `test_nodes` in `result.json`, backward-compat 4-tuple return from `_run_pytest_with_pythonpath`, and `_parse_report_jsonl` unit tests. |
| `test_harvest_validated_results.py` | **Harvest discovery tests** — 29 tests for `scripts/harvest_validated_results.py`: full discovery of `(image, run)` pairs from a fixture tree, `--image`/`--run`/`--card` filters and their composition, `results/` working-dir exclusion, `main()` analysis-dir creation (default bench, custom bench, custom `--output`), empty/missing `docker/` edge cases, and `_build_parser` defaults/flag acceptance. Loads script via `importlib` (not a package). |
| `test_harvest_rows.py` | **Harvest row-emission tests** — Tests for `build_rows_for_run()` and `harvest()` JSONL output (items 4–5). Covers: exact 4-row emission for two-card mixed fixture; all required keys present; `return int` equals row count; `harvested_at` uniform across rows; `complexity_tier` from `card_spec.json` (present/absent/mixed); rollup counts + `tests_hash` denormalized onto every node row; idempotency (truncate-write produces identical file on second run, no duplicate rows); ordering by `(image, run)` then card alphabetically; cards lacking `test_nodes` skipped gracefully (updated: now exercises legacy path); unreadable `result.json` skipped without crash. |
| `test_harvest_legacy.py` | **Legacy harvest branch tests** — Tests for `build_rows_for_run()` and `harvest()` when `result.json` has no `test_nodes` key (pre-items-1/2 data). Covers: `outcome="fail"` rows derived from `errors` strings; single `outcome="rollup"` / `test_node="__rollup__"` row carrying pass/fail/total; `tests_hash=None` for all legacy rows; `[legacy] <image>/<run>` notice printed by `harvest()`; de-duplication of repeated fail node IDs; collection-error lines without a real node ID mapped to `tests.py::<collection-error>`; empty/missing `errors` list produces only the rollup row; mixed modern+legacy cards in the same run produce the correct combined row set. |
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
| `test_card_filter.py` | **Card filter tests** — `--cards` CLI option parsing, collector-number normalization, workspace filtering. |
| `test_cli_docker.py` | **CLI Docker tests** — CLI flags, ContainerLifecycle mocking, docker args, harvest, smoke command, and per-image results path tests (`_image_dir`, `_image_results_dir`). |
| `test_cli_lifecycle_integration.py` | **CLI lifecycle integration tests** — End-to-end tests for ContainerLifecycle integration into CLI run/smoke commands. |
| `test_docker_entrypoints.py` | **Docker entrypoint tests** — Validates entrypoint.mjs files have system.log, agent_stdout.log, SIGTERM handler, no engine_work copy, no progress.jsonl writes. |
| `test_runner.py` | **Container lifecycle tests** — Poll-loop ordering, final read pass, timeout enforcement, snapshot callbacks for `ContainerLifecycle`. |
| `test_docker_direct_stream.py` | **Direct stream tests** — Tests for `_drain_pipe` direct streaming to run_dir and `_harvest_results` skip logic for already-present docker logs. |
| `test_snapshot_callback.py` | **Snapshot callback tests** — `snapshot_telemetry.jsonl` writing and callback wiring verification. |
| `test_cli_lifecycle_integration.py` | **CLI lifecycle integration tests** — End-to-end tests for ContainerLifecycle integration into CLI run/smoke commands (hang-timeout, harvest, lifecycle usage). |
| `test_runner_log.py` | **Runner log tests** — `_runner_log()` helper ISO-8601 timestamped file logging. |
| `test_telemetry.py` | **Telemetry tests** — FastTelemetry channel polling, callback invocation, system channel usage. |
| `test_telemetry_bootstrap.py` | **Telemetry bootstrap tests** — Bootstrap line emission on first `_poll_mtimes` pass. |
| `test_channel_visibility.py` | **Channel visibility tests** — 7-channel count, visibility polling for structurally-empty channels. |
| `test_logs_viewer.py` | **Log viewer tests** — Viewer tab rendering, channel visibility, event loop polling. |
| `test_progress_removal.py` | **Progress removal tests** — Verifies progress.jsonl is absent from telemetry, runner, and viewer. |
| `test_workspace_structure.py` | **Workspace structure tests** — CI-time structure assertion for `benchmarks/sos/workspace/`. |
| `test_smoke_lifecycle.py` | **Integration smoke test** — Container lifecycle smoke test using PID-tagged alpine image with teardown cleanup (skipped by default, requires `--run-integration`). |
| `test_pytest_infra.py` | **Pytest infrastructure tests** — Integration marker registration, pytest-timeout configuration. |
| `test_workspace.py` | **Workspace staging tests** — `stage_workspace` signature, workspace structure, card filtering, prompt generation. |

## Subdirectories

- **`engine/`** — Unit tests for all engine modules. See `tests/engine/DIRECTORY_SUMMARY.md`.
- **`cards/`** — Unit tests for card implementations (25 test files). See `tests/cards/DIRECTORY_SUMMARY.md`.
- **`benchmark/`** — Integration tests and helpers. See `tests/benchmark/DIRECTORY_SUMMARY.md`.
- **`integration/`** — Integration tests for workspace staging (`test_stage_workspace.py`).
- **`audited/`** — **Relocated to `benchmarks/sos/data/tests/audited/`**. Per-card audited test directories (fdn/ and sos/).

## Testing Approach

- **Deterministic**: All tests use `DeterministicPlayer` with scripted FIFO choices.
- **Unit + Integration**: Each module has its own test file; integration tests validate cross-module interactions.
- **Conventions**: Test classes `Test<Feature>`, test methods `test_<behavior>`. Fixtures use `_make_game()`, `_make_player()` patterns.
- **conftest.py hook**: Filters out benchmark functions that pytest would incorrectly collect as tests.
