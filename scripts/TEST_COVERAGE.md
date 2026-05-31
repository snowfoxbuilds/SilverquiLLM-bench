# Test Coverage — scripts/

## 1. Covered

- `discover_validated_runs()` — all filters (image, run, card, composed), results/ exclusion, empty/missing docker/, card_dirs population (`test_harvest_validated_results.py`)
- `discover_validated_runs()` — run_dir exact path structure (points into validated_results/), image/run field correctness (`test_harvest_validated_results_gaps.py`)
- `discover_validated_runs()` — run dir lacking cards/ subdir handled gracefully with empty card_dirs; card filter skips such runs (`test_harvest_validated_results_gaps.py`)
- `discover_validated_runs()` — deterministic sort order by (image, run), stable across calls, lexicographic on run names (`test_harvest_validated_results_gaps.py`)
- `main()` — analysis dir creation for default (sos) and custom bench names, --output override, no crash with all filters (`test_harvest_validated_results.py`)
- `main()` — default output path derivation for non-sos bench verified by directory path structure (`test_harvest_validated_results_gaps.py`)
- `_build_parser()` — defaults and all flag acceptance (`test_harvest_validated_results.py`)

## 2. Gaps (Not Yet Covered)

- `main()` — actual JSONL write logic (not yet implemented in the script; the script currently only prints a summary). Low priority until item 4 implements writing.

## 3. Edge Cases & Integration Gaps

- [x] Empty docker/ tree returns []
- [x] Missing docker/ dir returns []
- [x] run dir with no cards/ subdir returns empty card_dirs (no crash)
- [x] run dir with empty cards/ subdir returns empty card_dirs
- [x] results/ working dir excluded (not validated_results/)
- [x] run_dir path points into validated_results/, not results/
- [x] Sort order stable and correct for (image, run) pairs
- [ ] JSONL output file content (blocked on implementation)
