# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 4: Standardize per-card paths on card_dir_name

### Tests
- `tests/test_card_id_map.py` — card ID map JSON structure and build script tests
- `tests/test_harness.py` — AgentSession integration tests (blind, impl_test, timeout, aggregation)

### Implementation
- `silverquillm/agent_session.py` — added `card_id` field and `_path_id` property; updated path construction in `harvest_results()` and `run_card()` to use `_path_id`
- `silverquillm/cli.py` — pass `card_id=str(card_dir_name)` to AgentSession; fix regression postmortem path and agent_thoughts call to use card_dir_name/_path_id

## Item 5: Wire agent output through strategy → CardRunResult → postmortem

### Tests
- `tests/test_strategies.py` — updated expected fields set to include agent_output and prompt_used

### Implementation
- `silverquillm/strategies.py` — added agent_output and prompt_used fields to CardRunResult; capture adapter.run() return value in both strategies
- `silverquillm/agent_session.py` — use result.agent_output/result.prompt_used in postmortem and raw log calls; fixed postmortem status to binary success/error; preserve agent_output/prompt_used on violation path

## Item 6: Replace ThreadPoolExecutor with direct adapter call

### Tests
- `tests/test_strategies.py` — existing tests verify strategies call adapter.run() and handle timeout/completion/no_output

### Implementation
- `silverquillm/strategies.py` — removed ThreadPoolExecutor wrapping in both BlindStrategy and ImplTestStrategy; call adapter.run_with_retries(timeout=timeout, retries=0) directly to enforce timeout; removed unused concurrent.futures imports


## Item 7: Remove stale iterations/ directory creation

### Tests
- `tests/test_no_stale_iterations.py` — verifies no stale iterations references leak into serialized results

### Implementation
- `silverquillm/results.py` — removed stale iteration-count re-addition to blind/tested metrics in `_build_result_record()`; added `iteration_count` to `_IMPL_EXCLUDE` set; updated docstrings to remove `iterations` references
- `silverquillm/run_utils.py` — removed stale `"iterations": tested.iterations` assignment from save pipeline

## Item 8: Add signal handler for graceful interrupt cleanup

### Tests
- `tests/test_signal_handler.py` — tests for signal handler registration, restoration, and interrupt behavior

### Implementation
- `silverquillm/cli.py` — added signal handler, `_active_session` tracking, `KeyboardInterrupt` handling in card loop, and signal restoration in `try`/`finally` block

## Item 9: Add preflight workspace isolation check

### Tests
- `tests/test_preflight.py` — existing preflight tests (all 27 passing)

### Implementation
- `silverquillm/preflight.py` — added `_check_workspace_isolation()` function with canary UUID check; added `skip_isolation_check` parameter to `preflight_check()`; added `uuid` and `logging` imports; **revised**: adapter/setup exceptions now surface as preflight errors instead of being silently swallowed
- `silverquillm/cli.py` — added `--skip-isolation-check` CLI flag; passed `skip_isolation_check` to `preflight_check()`

## Item 10: Fix test_timeout_enforcement.py

### Tests
- `tests/test_timeout_enforcement.py` — 35 timeout enforcement tests (strategy-level, adapter kill, run_with_retries, process-group kill)

### Implementation
- `tests/test_timeout_enforcement.py` — converted `_BlockingAdapter` and `_BlockingNoKillAdapter` to proper `AgentAdapter` subclasses so they inherit `run_with_retries()`; patched `signal.signal`/`signal.alarm` on `TestRunWithRetriesDeadline` class to prevent real SIGALRM; forced threading timeout path via `_run_with_timeout` patch; patched `os.getpgid`/`os.killpg` on `test_kill_noop_*` methods for safety

## Item 11: Add run_summary.json top-level aggregation

### Tests
- `tests/test_aggregator.py` — 23 tests for run-level aggregation, CLI aggregate subcommand, and edge cases

### Implementation
- No changes needed — `silverquillm/aggregator.py` already has `RunSummary`, `aggregate_run()`, and `save_run_summary_v2()`; `silverquillm/cli.py` already wires aggregation after the card loop and provides the `aggregate` subcommand

## Item 12: Simplify or remove rules_skill.py

### Tests
- `tests/test_rules_skill.py` — existing 18 tests for download, index, lookup, and rules_overview.md
- `tests/test_package_rename.py` — verifies silverquillm.rules_skill is importable

### Implementation
- `silverquillm/rules_skill.py` — simplified from 26KB/650 lines to 5.6KB/173 lines; removed inline _STUB_RULES constant, generate_rules_overview, and _RULES_OVERVIEW_CONTENT; kept same public API (download_comprehensive_rules, build_rules_index, lookup_rule); added minimal embedded fallback rules string for when both network and cache are unavailable

## Item 13: Fix PROJECT_MAP.md ASCII art alignment

### Implementation
- `PROJECT_MAP.md` — realigned ASCII art boxes in architecture diagram

## Item 14: Fix get_targets() snapshot-at-call-time issue

### Tests
- `tests/engine/test_lazy_targets.py` — 10 tests verifying lazy filter evaluation (creature added after filter creation, non-creature rejection, keyword changes, power changes, controller changes, toughness changes, card type changes, base get_targets, multiple requirements, zone removal)

### Implementation
- `engine/types.py` — Updated TargetRequirement docstring to document lazy filter convention
- `engine/casting.py` — Wired filter_fn validation into cast_spell target selection (step 5)
- `cards/foundations/simple_spells_batch3.py` — Replaced snapshot filter_fn lambdas with lazy predicates; restored controller/ownership checks for SnakeskinVeil, DivineResilience, BiteDown, FellingBlow, Zombify; restored different-controllers validation for RunAwayTogether in on_resolve
- `cards/foundations/simple_spells.py` — Replaced snapshot filter_fn lambdas with lazy predicates; restored graveyard ownership check for CemeteryRecruitment
- `cards/foundations/auras_batch2.py` — Replaced 10 snapshot filter_fn lambdas with lazy property-based predicates
- `cards/foundations/enchantments.py` — Replaced 4 snapshot filter_fn lambdas with lazy property-based predicates
- `cards/foundations/simple_permanents.py` — Replaced 3 snapshot filter_fn lambdas with lazy property-based predicates
- `cards/foundations/global_enchantments.py` — Replaced 1 snapshot filter_fn lambda with lazy predicate including controller check

## Item 15: Refactor chosen_targets off card instance

### Tests
- `tests/engine/test_casting.py` — existing casting pipeline tests (all 1133 engine tests pass)
- `tests/audited/fdn/` — existing card tests (all 1487 FDN tests pass)

### Implementation
- `engine/casting.py` — `_resolve_spell()` now accepts `StackObject` and reads `obj.targets` directly (single source of truth); removed `targets_snapshot` copy; sets `card.chosen_targets = obj.targets` at resolve time
- `engine/card.py` — updated `on_resolve` docstring to document resolve-time target availability
