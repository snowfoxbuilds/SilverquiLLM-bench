# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Expand _check_violations to cover all protected directories

### Tests
- `tests/test_agent_session.py` — existing session tests (all 35 pass unchanged)

### Implementation
- `benchmark/agent_session.py` — Added `_PROTECTED_DIRS` constant, `_snapshot_all_protected` helper, rewrote `_check_violations` to return `list[str]` covering all protected dirs; added deletion detection (before-vs-after diff for missing paths)


## Item 2: Wire enhanced violation checks into both agent run methods

### Tests
- `tests/test_agent_session.py` — existing session tests (35 pass unchanged)
- `tests/test_check_violations.py` — violation detection tests (17 pass unchanged)

### Implementation
- `benchmark/agent_session.py` — Wired `_snapshot_all_protected` and list-returning `_check_violations` into both `run_blind_implementation` (renamed var, added logging) and `run_test_informed` (added per-round snapshot+check with violation early-return); moved metrics accounting before violation check so violating round's tokens/context/rules are included


## Item 3: Add card-spec loading and filtering utility

### Tests
- `tests/test_card_loader.py` — 14 tests covering load_card_specs, load_prototype_cards, filter_by_collectors, filter_by_prototype

### Implementation
- `benchmark/card_loader.py` — New module with load_card_specs, load_prototype_cards, filter_by_collectors, and filter_by_prototype utilities for CLI card selection; improved docstring for load_prototype_cards

## Item 4: Add --cards, --prototype, and --dry-run flags to benchmark run

### Tests
- `tests/test_cli_run_flags.py` — 9 tests covering --dry-run, --cards, --prototype, mutual exclusion, and error handling
- `tests/test_cli_config.py` — existing CLI tests (31 passing, no regressions)

### Implementation
- `benchmark/cli.py` — Added --cards, --prototype, --dry-run flags; replaced classified-data loading with card_loader functions; wrapped load_card_specs/filter_by_collectors/filter_by_prototype in try/except to surface CLI errors

## Item 5: Wire benchmark run orchestration loop

### Tests
- `tests/test_cli_orchestration.py` — 8 tests covering orchestration loop, result saving, progress output, skip logic
- `tests/test_cli_config.py` — existing CLI tests (31 passing, updated test_run_loads_config to use --dry-run)
- `tests/test_cli_run_flags.py` — existing flag tests (9 passing, no regressions)

### Implementation
- `benchmark/cli.py` — Added orchestration loop with finally-based cleanup, failure tracking, and non-zero exit on card failures
- `benchmark/run_utils.py` — New module with _session_results_to_dicts helper for dataclass-to-dict conversion with source file reading
- `tests/test_cli_config.py` — Added --dry-run to test_run_loads_config (test predates orchestration loop)

## Item 6: Wire benchmark run post-loop: self-eval and summary

### Tests
- `tests/test_cli_orchestration.py` — existing orchestration tests (8 passing, no regressions)
- `tests/test_evaluator.py` — existing evaluator tests (36 passing, no regressions)

### Implementation
- `benchmark/evaluator.py` — Added `run_self_eval_flat` function for flat card directory layout
- `benchmark/cli.py` — Wired post-loop self-eval, result.json merge (with phase-level errors matching _build_result_record schema), save_run_summary, and summary printing with elapsed time

## Item 7: Wire benchmark eval command

### Tests
- `tests/test_cli_config.py` — existing CLI tests (31 passing, no regressions)
- `tests/test_post_loop_eval.py` — existing evaluator tests (passing, no regressions)

### Implementation
- `benchmark/cli.py` — Replaced eval stub with full implementation: scan run dirs, detect agents from config.yaml, run self-eval flat for single-agent, audited eval with --audited-tests, deduplicate by (agent, card_id, eval_type) keeping latest run, save results.json, print summary
