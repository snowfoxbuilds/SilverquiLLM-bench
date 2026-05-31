# Test Coverage — silverquillm/evaluator.py (Item 1 scope)

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

## 2. Gaps (Not Yet Covered)

None identified for the Item 1 feature scope.

## 3. Edge Cases & Integration Gaps

- [x] SHA-256 value correctness
- [x] Determinism across runs
- [x] Hash changes when file content changes
- [x] Missing audited test file (skipped path)
- [x] Missing card_impl.py (error path, no result.json)
- [x] FDN path excluded from stamping
- [x] `asdict` serialization round-trip
- [x] Field presence and default
