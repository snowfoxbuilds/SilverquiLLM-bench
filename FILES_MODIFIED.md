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
