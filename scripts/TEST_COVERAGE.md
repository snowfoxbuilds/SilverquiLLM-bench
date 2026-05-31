# Test Coverage — scripts/

## 1. Covered

- `discover_validated_runs()` — all filters (image, run, card, composed), results/ exclusion, empty/missing docker/, card_dirs population (`test_harvest_validated_results.py`)
- `discover_validated_runs()` — run_dir exact path structure (points into validated_results/), image/run field correctness (`test_harvest_validated_results_gaps.py`)
- `discover_validated_runs()` — run dir lacking cards/ subdir handled gracefully with empty card_dirs; card filter skips such runs (`test_harvest_validated_results_gaps.py`)
- `discover_validated_runs()` — deterministic sort order by (image, run), stable across calls, lexicographic on run names (`test_harvest_validated_results_gaps.py`)
- `main()` — analysis dir creation for default (sos) and custom bench names, --output override, no crash with all filters (`test_harvest_validated_results.py`)
- `main()` — default output path derivation for non-sos bench verified by directory path structure (`test_harvest_validated_results_gaps.py`)
- `_build_parser()` — defaults and all flag acceptance (`test_harvest_validated_results.py`)
- `build_rows_for_run()` / `harvest()` — two-card mixed pass/fail integration, return count, harvested_at uniformity, complexity_tier present/absent, denormalization, idempotency, ordering, legacy-skip (`test_harvest_rows.py`)
- `build_rows_for_run()` — test_nodes=[] (empty list, key present) emits zero rows (`test_harvest_rows_gaps.py`)
- `harvest()` — --image filter narrows emitted rows to matching image only (`test_harvest_rows_gaps.py`)
- `harvest()` — --card filter narrows emitted rows to matching card only (`test_harvest_rows_gaps.py`)
- `build_rows_for_run()` — malformed/invalid JSON result.json skipped without crashing; sibling cards still emit (`test_harvest_rows_gaps.py`)
- `harvest()` — JSONL output is valid one-object-per-line; each line independently json-loads as dict (`test_harvest_rows_gaps.py`)
- `build_rows_for_run()` / `harvest()` — legacy back-compat: fail rows from errors, __rollup__ row, tests_hash=null, dedup, unparseable errors, missing fields, rollup outcome sentinel, stray tests_hash, node-id normalization (`test_harvest_legacy.py`)
- `harvest()` — per-run [legacy] notice printed once per legacy run, not for modern runs (`test_harvest_legacy.py`)
- `harvest()` — mixed legacy+modern run in same image/run: [legacy] notice printed once AND modern per-node rows plus legacy fail+rollup rows all emitted correctly (`test_harvest_legacy_gaps.py`)
- `_extract_fail_nodes_from_errors()` — FAILED line with '::' in reason text produces exactly one fail row with correct test_node, no bogus extra nodes (`test_harvest_legacy_gaps.py`)
- `harvest()` — image= filter on all-legacy image yields only rollup/fail rows, no modern pass rows, no crash (`test_harvest_legacy_gaps.py`)

## 2. Gaps (Not Yet Covered)

None — all identified gaps for items 4 and 5 are now covered.

## 3. Edge Cases & Integration Gaps

- [x] Empty docker/ tree returns []
- [x] Missing docker/ dir returns []
- [x] run dir with no cards/ subdir returns empty card_dirs (no crash)
- [x] run dir with empty cards/ subdir returns empty card_dirs
- [x] results/ working dir excluded (not validated_results/)
- [x] run_dir path points into validated_results/, not results/
- [x] Sort order stable and correct for (image, run) pairs
- [x] JSONL output: each line independently valid JSON
- [x] test_nodes=[] (empty list) emits zero rows
- [x] --image filter narrows harvest output
- [x] --card filter narrows harvest output
- [x] Malformed (invalid JSON) result.json skipped gracefully
- [x] Mixed legacy+modern run: [legacy] notice once, both row types emitted
- [x] FAILED reason text containing '::' does not produce extra nodes
- [x] image= filter on all-legacy image: only rollup/fail rows, no crash
