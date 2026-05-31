# Test Coverage Map

| Directory | Status | Summary | Coverage File |
|-----------|--------|---------|---------------|
| `silverquillm/` | [Completed] | `tests_hash` and `test_nodes` features on `CardResult` fully covered; added 18 gap tests in `test_test_nodes_gaps.py` for skipped/xfail exclusion, unknown-outcome ignoring, `_normalize_nodeid` path-only branch, and cleanup guarantees. Also fixed an implementation bug where xfail outcomes were incorrectly captured as "fail". | [silverquillm/TEST_COVERAGE.md](silverquillm/TEST_COVERAGE.md) |
| `scripts/` | [Completed] | `harvest_validated_results.py` discovery and CLI fully covered; Tester's 29 tests cover filters, CLI dir creation, edge cases; added 14 gap tests in `test_harvest_validated_results_gaps.py` for run_dir exact path structure, missing-cards/ subdir graceful handling, --output default path derivation for non-sos bench, and deterministic ordering guarantees. | [scripts/TEST_COVERAGE.md](scripts/TEST_COVERAGE.md) |
