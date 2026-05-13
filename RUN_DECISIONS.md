# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Disagreement: Item 6 — Replace ThreadPoolExecutor
- **Reviewer comment (strict)**: Strategies must enforce timeout via `run_with_retries()`, not bare `adapter.run()`.
- **Implementer justification**: Test mocks don't have `run_with_retries()`; tests encode a `run()` contract.
- **Coordinator decision**: accept reviewer
- **Reasoning**: The TODO spec explicitly says to use `run_with_retries(prompt, workspace, timeout=timeout, retries=0)`. Without it, a blocking adapter hangs forever in production. The Tester wrote mocks that don't match the spec's intent — the mocks need fixing, not the architecture. Having the Tester rewrite the timeout mocks to include `run_with_retries` (or subclass `AgentAdapter`), then the Implementer can use it.
- **Impact**: `silverquillm/strategies.py`, timeout-related tests.
