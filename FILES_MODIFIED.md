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
