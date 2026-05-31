# Test Coverage Map

| Directory | Status | Summary | Coverage File |
|-----------|--------|---------|---------------|
| `silverquillm/` | [Completed] | `tests_hash` and `test_nodes` features on `CardResult` fully covered; added 18 gap tests in `test_test_nodes_gaps.py` for skipped/xfail exclusion, unknown-outcome ignoring, `_normalize_nodeid` path-only branch, and cleanup guarantees. Also fixed an implementation bug where xfail outcomes were incorrectly captured as "fail". | [silverquillm/TEST_COVERAGE.md](silverquillm/TEST_COVERAGE.md) |
| `scripts/` | [Completed] | `harvest_validated_results.py` discovery, CLI, JSONL row emission, and legacy back-compat fully covered; added 5 gap tests in `test_harvest_legacy_gaps.py` for mixed legacy+modern notice+rows, '::'-in-reason non-regression, and image-filtered all-legacy harvest. | [scripts/TEST_COVERAGE.md](scripts/TEST_COVERAGE.md) |
