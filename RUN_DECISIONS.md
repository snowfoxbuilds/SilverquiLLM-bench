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
