# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Stamp tests_hash into per-card SOS result.json

### Implementation
- `silverquillm/evaluator.py` — Added `tests_hash: str = ""` field to `CardResult` dataclass and SHA-256 hashing of audited test file in `_eval_sos_cards` before result.json write

### Tests
- `tests/test_tests_hash.py` — 13 test cases verifying tests_hash correctness (SHA-256 match), determinism, change-on-edit, missing-file edge case, and additive-only preservation of existing CardResult fields

## Item 2: Record per-test-node pass/fail outcomes in result.json

### Implementation
- `silverquillm/evaluator.py` — Added `test_nodes` field to `CardResult`, inline conftest-based report capture in `_run_pytest_with_pythonpath`, JSONL parser, nodeid normalization, and population in `_eval_sos_cards`

### Tests
- `tests/test_test_nodes.py` — 29 test cases verifying per-node capture (real pytest), nodeid normalization, count consistency, collection/setup error handling, JSON persistence round-trip, back-compat 4-tuple return, and _parse_report_jsonl unit tests

## Item 3: Scaffold scripts/harvest_validated_results.py (discovery + CLI)

### Implementation
- `scripts/harvest_validated_results.py` — New utility script with discover_validated_runs() function, ValidatedRun dataclass, argparse CLI (--bench/--output/--image/--run/--card), and discovery summary output
- `benchmarks/sos/analysis/.gitkeep` — Created analysis output directory for harvested results

### Tests
- `tests/test_harvest_validated_results.py` — 29 test cases validating discovery of (image, run) pairs from fixture tree, --image/--run/--card filters and composition, results/ working dir exclusion, CLI analysis-dir creation, empty/missing docker/ edge cases, and parser defaults

## Item 4: Emit long-format harvested_results.jsonl rows

### Implementation
- `scripts/harvest_validated_results.py` — Added build_rows_for_run() row builder, _read_complexity_tier() helper, harvest() orchestrator (discovers runs, writes JSONL, returns row count), and refactored main() to delegate to harvest()

### Tests
- `tests/test_harvest_rows.py` — 18 test cases validating JSONL row emission: integration test with two-card mixed pass/fail fixture, return value, harvested_at determinism, complexity_tier present/absent, denormalized rollup counts, idempotency (truncate mode), row ordering by (image, run, card), and legacy/missing test_nodes skipping

## Item 5: Back-compat harvest for legacy Validated Results

### Implementation
- `scripts/harvest_validated_results.py` — Added legacy path in build_rows_for_run: _FAILED_RE regex, _normalize_nodeid, _extract_fail_nodes_from_errors helpers; legacy detection on test_nodes key absence; fail-row derivation from errors; __rollup__ row with outcome="rollup"; tests_hash=None for legacy; per-run legacy notice in harvest() via __rollup__ row detection; build_rows_for_run returns list[dict] (not tuple)

### Tests
- `tests/test_harvest_rows.py` — Updated 2 stale Item-4 placeholder tests (TestMissingTestNodes) to assert new legacy rollup behavior instead of 0-row skipping
- `tests/test_harvest_legacy.py` — 20 new test cases: core spec (fail rows from errors, rollup row, tests_hash=None, no pass rows), de-duplication, unparseable/collection errors, missing errors/counts fields, rollup outcome validation, per-run legacy notice via capsys, stray tests_hash ignored, node-ID normalization
