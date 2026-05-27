# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Spec deviation: Item 1 — evaluator.py not modified
- **TODO spec expected**: Extend `silverquillm/evaluator.py` with `--against=oracle` mode.
- **Actual codebase state**: The harness is self-contained in `tests/test_audited_against_reference.py` and reuses the temp-dir pattern from evaluator.py without modifying it.
- **What was implemented instead**: Standalone test file that pytest collects directly, no evaluator flag needed.
- **Impact**: `tests/test_audited_against_reference.py` — simpler integration, fewer moving parts.

