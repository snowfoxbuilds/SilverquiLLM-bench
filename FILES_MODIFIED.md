# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 7: Enforce timeout_per_card (fixes Issue #14)

### Tests
- `tests/test_timeout_enforcement.py` — Tests for hard timeout enforcement at strategy and adapter level

### Implementation
- `silverquillm/strategies.py` — Call adapter.kill() on timeout in both BlindStrategy and ImplTestStrategy
- `silverquillm/adapters/base.py` — Added kill() no-op to AgentAdapter; run_with_retries calls self.kill() before raising TimeoutError
- `silverquillm/adapters/opencode.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/aider.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/claude_code.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/pi.py` — Track _process, start_new_session=True, kill via os.killpg process-group

## Item 8: Move all evaluation to post-run

### Tests
- `tests/test_post_eval.py` — Tests for CardEvalResult dataclass, run_post_eval flow, self-eval, audited eval, result.json persistence, CLI integration

### Implementation
- `silverquillm/post_eval.py` — New module with `CardEvalResult` dataclass and `run_post_eval()` function; deterministic audited test lookup via `_resolve_audited_tests()`
- `silverquillm/evaluator.py` — Added `engine_dir` parameter to `run_tests()` for PYTHONPATH customization
- `silverquillm/cli.py` — Replaced inline self-eval loop with `run_post_eval()` call after card loop

### Implementation
- `silverquillm/evaluator.py` — Added `EvalResultV2` dataclass with mode-aware v2 schema alongside existing `EvalResult`
- `silverquillm/results.py` — Added `save_card_result_v2()`, `load_card_result()`, and `_normalise_to_v2()` with full v1→v2 normalization including implementation flattening
- `silverquillm/scorer.py` — Updated `_load_eval_results()` to normalise v2 records; `_v2_to_eval_dicts()` now respects mode for blind/tested column selection
- `silverquillm/cli.py` — Wired `save_card_result_v2()` to overwrite result.json with v2 schema after card processing
- `silverquillm/post_eval.py` — Updated `_merge_result_json()` to write v2 schema with schema_version and mode fields

## Item 10: Automatic run_summary.json aggregation

### Tests
- `tests/test_aggregator.py` — Tests for aggregate_run() pure function, RunSummary dataclass, persistence, and idempotency

### Implementation
- `silverquillm/aggregator.py` — New module with RunSummary dataclass, aggregate_run() pure function, save_run_summary_v2(); revised: deterministic timestamp from result.json mtime, integer token handling, legacy status normalization
- `silverquillm/cli.py` — Imported aggregator, call aggregate_run after post-eval in run command, added `benchmark aggregate` subcommand

## Item 11: Allowlist-based contamination checker

### Tests
- `tests/test_allowlist_contamination.py` — 23 tests for allowlist-based contamination detection

### Implementation
- `silverquillm/agent_session.py` — Rewrote `_snapshot_all_protected()` to walk entire repo tree (not just `_PROTECTED_DIRS`); `_check_violations()` uses allowlist via `_is_allowed_path()` helper with `_ALLOWED_DIRS` (engine/) and `_IGNORED_SUFFIXES` (.pyc/.pyo/.log)
## Item 12: Fix test_utils.md import path (fixes Issue #11)

### Implementation
- `docs/test_utils.md` — Updated all import examples and prose from `tests.test_utils` to `test_utils`

## Item 13: Add GameState to template imports (fixes Issue #12)

### Implementation
- `silverquillm/template_gen.py` — Added `from engine.game_state import GameState` to generated template import block

## Item 14: Simplify postmortem schema

### Tests
- `tests/test_postmortem_schema_v2.py` — 26 tests for structured event helpers and raw log schema
- `tests/test_postmortem_logging.py` — Existing postmortem JSONL logging tests (18 tests, all passing)

### Implementation
- `silverquillm/agent_session.py` — Added _append_file_written, _append_eval_result, _append_regression_check event helpers; removed phase/round from append_raw_log; wired _append_file_written into harvest_results()
- `silverquillm/post_eval.py` — Wired _append_eval_result into self-eval and audited-eval paths in run_post_eval()
- `silverquillm/cli.py` — Wired _append_regression_check into regression loop after run_regressions()

## Item 15: Pre-flight validation at run start

### Tests
- `tests/test_preflight.py` — 18 tests for preflight validation (card_specs_dir, config, workspace, template imports, test_utils, happy path, error aggregation)

### Implementation
- `silverquillm/preflight.py` — New module with `preflight_check()`, `PreflightError`, and individual check functions for imports, workspace, .workspace/ dir, engine test suite, config, and card_specs_dir; revised: added `_check_engine_tests()` subprocess pytest, `_check_workspace_dir()` for .workspace/, enhanced `_check_test_utils_import()` with actual import verification
- `silverquillm/cli.py` — Import and call `preflight_check()` before card loop in `run()` command
