# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Test failure: Item 1 — Add mode to config and create CardStrategy ABC
- **Failing tests**: `TestMaxTestRoundsRemoved::test_agent_config_has_no_max_test_rounds`
- **Tester's intent**: Verify the TODO's explicit requirement that `max_test_rounds` is removed from `AgentConfig`.
- **Implementer's approach**: Retained `max_test_rounds` because pre-existing tests still asserted it.
- **Coordinator decision**: fix implementation
- **Reasoning**: The TODO explicitly removes harness-managed iteration and says `max_test_rounds` is no longer used. Pre-existing consumers/tests should be migrated to the new mode-based contract rather than preserving the obsolete field.

## Test baseline note: Item 1 — full-suite audited SOS failure
- **Context**: The item 1 revision reported all targeted tests passing and one unrelated full-suite failure in `tests/audited/sos/1/tests.py`.
- **Decision**: Proceed with the item because the failure is outside the Phase 7 harness/config surface and appears to be part of the known audited SOS stub-failure baseline from prior work.
- **Reasoning**: The item-specific tests and affected consumer tests passed; fixing audited SOS oracle/stub behavior is unrelated to the mode/strategy config refactor.
- **Alternatives considered**: Block item 1 until every audited SOS behavior test passes.
- **Impact**: No code impact for item 1; later audit/final test reporting should preserve this context if the full suite remains red.

## Item 2 — BlindStrategy timeout enforcement
- **Context**: `BlindStrategy.run_card()` must return `timeout` when the supplied per-card timeout expires, but the adapter interface remains synchronous and does not accept a timeout argument.
- **Decision**: Enforce the item-level timeout by running `adapter.run()` through a `ThreadPoolExecutor` and mapping `concurrent.futures.TimeoutError`, built-in `TimeoutError`, and `subprocess.TimeoutExpired` to `CardRunStatus.timeout`.
- **Reasoning**: This keeps the strategy API independent of specific adapter implementations while satisfying the item requirement for a hard status transition.
- **Alternatives considered**: Rely solely on adapter-level timeout handling; rejected because the strategy's `timeout` parameter would remain unenforced.
- **Impact**: `silverquillm/strategies.py`.

## Item 3 — Strategy timeout shutdown behavior
- **Context**: The first shared timeout implementation used a `ThreadPoolExecutor` context manager, which would block on `shutdown(wait=True)` after `future.result(timeout=...)` raised.
- **Decision**: Manage the executor explicitly and call `shutdown(wait=False, cancel_futures=True)` on timeout so `run_card()` returns `CardRunStatus.timeout` promptly for both blind and impl-test strategies.
- **Reasoning**: The strategy status must reflect the supplied timeout even if a synchronous adapter keeps running internally.
- **Alternatives considered**: Keep the context-manager pattern; rejected because it can hang past the requested timeout.
- **Impact**: `silverquillm/strategies.py`.
