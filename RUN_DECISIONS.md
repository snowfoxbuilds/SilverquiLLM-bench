# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Spec deviation: Item 1 — evaluator.py not modified
- **TODO spec expected**: Extend `silverquillm/evaluator.py` with `--against=oracle` mode.
- **Actual codebase state**: The harness is self-contained in `tests/test_audited_against_reference.py` and reuses the temp-dir pattern from evaluator.py without modifying it.
- **What was implemented instead**: Standalone test file that pytest collects directly, no evaluator flag needed.
- **Impact**: `tests/test_audited_against_reference.py` — simpler integration, fewer moving parts.

## Test infrastructure: conftest for oracle workspace audited tests
- **Context**: Tests in `test_oracle_workspace/tests/audited/sos/` need to import from `card_impl` generically.
- **Decision**: Created a conftest in the workspace that resolves `card_impl` imports by detecting the collector directory and loading from `cards/sos/<dir>/card_impl.py`.
- **Reasoning**: Matches the pattern used in the canonical audited test conftest; makes tests impl-agnostic.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/conftest.py`

## Design: sos_13 dual-mode card (front creature + back instant)
- **Context**: Emeritus of Truce // Swords to Plowshares is a split card with prepared mechanic.
- **Decision**: Single class with `_casting_back_face` flag. Mode detected in `can_cast()` when card is in exile + prepared. `get_targets()` and `on_resolve()` branch on this flag.
- **Reasoning**: Simpler than separate instant class; the `cast_spell_free` flow operates on same card object from exile.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_13/card_impl.py`

