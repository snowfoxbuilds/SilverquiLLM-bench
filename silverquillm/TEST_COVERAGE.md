# Test Coverage — silverquillm/evaluator.py (Items 1 & 2 scope)

## 1. Covered

- **`CardResult.tests_hash` field** — `test_tests_hash.py::TestCardResultTestsHashField`
  - Field exists, default is `""`, type is `str`, serializes via `asdict`.

- **SHA-256 correctness** — `test_tests_hash.py::TestTestsHashCorrectValue`
  - `result.json` and in-memory `CardResult.tests_hash` equal `sha256(tests.py bytes).hexdigest()`.
  - Hash is 64 lowercase hex characters.

- **Determinism** — `test_tests_hash.py::TestTestsHashDeterminism`
  - Same audited `tests.py` produces identical hash across two evaluations.

- **Hash changes on edit** — `test_tests_hash.py::TestTestsHashChangesOnEdit`
  - Different `tests.py` content produces different hash; cross-checked against independent computation.

- **Missing audited test file** — `test_tests_hash.py::TestTestsHashMissingTestFile`
  - `tests_hash=""`, card marked `skipped=True`, errors recorded, evaluate() does not crash, counts are zero.

- **Additive-only: existing fields preserved** — `test_tests_hash.py::TestAdditiveChange`
  - All pre-existing `CardResult` fields still present; `result.json` carries them all.

- **Missing `card_impl.py` branch** — `test_tests_hash_gaps.py::TestTestsHashMissingCardImpl`
  - `tests_hash=""`, no `result.json` written, error message references `card_impl`.

- **FDN path does not stamp `tests_hash`** — `test_tests_hash_gaps.py::TestTestsHashNotStampedForFDN`
  - FDN `CardResult` objects always have `tests_hash=""` (feature scoped to SOS only).

- **`test_nodes` per-node capture** — `test_test_nodes.py` (29 tests)
  - Real pass/fail capture via subprocess pytest, nodeid normalization, count consistency,
    collection/setup error handling, JSON persistence, 4-tuple back-compat.

- **Skipped/xfail NOT enumerated** — `test_test_nodes_gaps.py::TestSkippedXfailNotEnumerated`
  - `@pytest.mark.skip` tests absent from `test_nodes`; do not inflate fail count.
  - `@pytest.mark.xfail` tests absent from `test_nodes`; do not inflate fail count.
  - Only the passing test appears when a file mixes pass + skip.

- **`_parse_report_jsonl` unknown/non-pass-fail outcomes ignored** — `test_test_nodes_gaps.py::TestParseReportJsonlUnknownOutcomes`
  - `skipped`, `xfail`, `xpass`, missing outcome, unknown strings all silently ignored.
  - Malformed JSON lines silently skipped.

- **`_normalize_nodeid` path-without-separator branch** — `test_test_nodes_gaps.py::TestNormalizeNodeidEdgeCases`
  - Path-only string (no `::`) with `/` returns basename.
  - Already-normalized IDs returned unchanged.
  - Deep nested path + `::` correctly stripped.

- **Guaranteed cleanup** — `test_test_nodes_gaps.py::TestCleanupAfterCapture`
  - No leftover `conftest.py` after successful run.
  - No leftover `conftest.py` after test failure.
  - Pre-existing `conftest.py` restored to original content after capture.

## 2. Gaps (Not Yet Covered)

None identified for the Items 1 & 2 feature scope.

## 3. Edge Cases & Integration Gaps

- [x] SHA-256 value correctness
- [x] Determinism across runs
- [x] Hash changes when file content changes
- [x] Missing audited test file (skipped path)
- [x] Missing card_impl.py (error path, no result.json)
- [x] FDN path excluded from stamping
- [x] `asdict` serialization round-trip
- [x] Field presence and default
- [x] Skipped tests not enumerated in `test_nodes`
- [x] xfail tests not enumerated in `test_nodes`
- [x] Unknown outcome values ignored by `_parse_report_jsonl`
- [x] Malformed JSON lines ignored by `_parse_report_jsonl`
- [x] `_normalize_nodeid` path-without-`::` branch
- [x] Cleanup of injected conftest after success and failure
- [x] Restore of pre-existing conftest after capture
