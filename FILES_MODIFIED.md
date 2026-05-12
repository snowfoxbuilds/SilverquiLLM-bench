# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Add mode to config and create CardStrategy ABC

### Tests
tests/test_strategies.py — 29 tests for mode field, CardStrategy ABC, CardRunResult, CardRunStatus, get_strategy, max_test_rounds removal

### Implementation
- `silverquillm/config.py` — Added `mode` field to `BenchmarkConfig` with validation; removed `max_test_rounds` from `AgentConfig`
- `silverquillm/strategies.py` — New module with `CardStrategy` ABC, `CardRunResult` dataclass, `CardRunStatus` enum, `BlindStrategy`/`ImplTestStrategy` stubs, and `get_strategy()` factory
- `silverquillm/agent_session.py` — Replaced `config.agent.max_test_rounds` with `_DEFAULT_MAX_ROUNDS` constant
- `config.example.yaml` — Added `mode: "impl_test"` field; removed `max_test_rounds` from agent block
- `tests/test_agent_config.py` — Removed all `max_test_rounds` references from AgentConfig tests
- `tests/test_postmortem_logging.py` — Removed `max_test_rounds` from AgentConfig constructors
- `tests/test_agent_session_adapter.py` — Removed `max_test_rounds` from AgentConfig constructor
- `tests/test_agent_session.py` — Removed `max_test_rounds` from AgentConfig constructor; updated iteration assertion
- `tests/test_persistent_engine.py` — Removed `max_test_rounds` from AgentConfig constructor
- `tests/test_integration_helpers.py` — Removed `max_test_rounds` assertion
- `tests/test_cli_config.py` — Removed `max_test_rounds` tests and assertions
- `tests/test_config_consumers.py` — Updated field expectations, source audit patterns, and access tests
- `tests/benchmark/test_helpers.py` — Removed `max_test_rounds` from AgentConfig constructor
- `tests/test_violation_wiring.py` — Removed `max_test_rounds` from AgentConfig constructor in `_make_config` fixture

## Item 2: Implement BlindStrategy

### Implementation
- `silverquillm/strategies.py` — Implemented `BlindStrategy.run_card()` with prompt dispatch, timeout handling, and card_impl.py existence check
- `silverquillm/prompts.py` — Added `blind_mode_prompt()` and `_BLIND_MODE_TEMPLATE` that omits test_utils from workspace listing

## Item 3: Implement ImplTestStrategy

### Implementation
- `silverquillm/strategies.py` — Implemented `ImplTestStrategy.run_card()` with single prompt dispatch, timeout handling, and card_impl.py/tests.py detection
- `silverquillm/prompts.py` — Added `impl_test_mode_prompt()` and `_IMPL_TEST_MODE_TEMPLATE` combining impl + test instructions with test_utils references

## Item 4: Refactor agent_session.py remove harness-managed iteration

### Tests
tests/test_agent_session_refactor.py — 24 tests for harness removal, run_card delegation, harvest_results, workspace mode dependency

### Implementation
- `silverquillm/agent_session.py` — Removed _DEFAULT_MAX_ROUNDS, iteration_feedback_prompt import, _run_pytest, run_blind_implementation, run_test_informed; added test_utils.md copy for impl_test mode; added violation checking, postmortem logging, and agent_thoughts generation in run_card()
- `silverquillm/cli.py` — Updated orchestration to use run_card(); added impl_test mode TestInformedResult representation; changed regression registration to use card_impl.py
- `tests/test_agent_session.py` — Rewrote TestRunBlind/TestRunTestInformed to use strategy mocking
- `tests/test_agent_session_adapter.py` — Updated adapter invocation tests to use run_card()
- `tests/test_cli_orchestration.py` — Updated patches to use run_card instead of old methods
- `tests/test_postmortem_logging.py` — Added TestRunCardPostmortem class with integration tests exercising run_card() postmortem flow
- `tests/test_violation_wiring.py` — Added TestRunCardViolationWiring class with tests exercising run_card() violation checking flow
- `tests/benchmark/test_e2e.py` — Updated to use run_card() with adapter mock


## Item 5: Decouple harvest_results from violation status

### Implementation
- `silverquillm/strategies.py` — Added `violations: list[str]` field to `CardRunResult` dataclass
- `silverquillm/agent_session.py` — Updated `run_card()` to populate `violations` field in `CardRunResult` when violations detected
- `silverquillm/cli.py` — Propagate `card_run_result.violations` into `blind_dict` before `save_card_result()` so violations appear in `result.json`
- `silverquillm/results.py` — `_build_result_record()` extracts violations from result dicts and includes as top-level field in result.json
- `tests/test_results.py` — Added `TestViolationsInResultJson` class with 3 tests for violations in result.json
- `tests/test_harvest_unconditional.py` — New test file: 7 tests verifying violations annotate result and harvest runs unconditionally
- `tests/test_strategies.py` — Updated `test_has_expected_fields` to include `violations` in expected field set

## Item 6: Engine snapshot and rollback on timeout

### Tests
- `tests/test_engine_snapshot.py` — 20 tests for snapshot/restore functions and run_card integration with timeout rollback
- `tests/test_engine_snapshot_timeout_result.py` — 3 tests for production-like timeout-result path engine rollback

### Implementation
- `silverquillm/agent_session.py` — Added snapshot_engine() and restore_engine_snapshot() functions; integrated snapshot/rollback into run_card() flow; handles both exception-raised and result-status timeouts
- `tests/test_engine_snapshot_timeout_result.py` — New test file: 3 tests verifying engine rollback on CardRunResult(status=timeout)
