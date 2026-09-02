# Test Coverage — scripts/

## 1. Covered

- `discover_validated_runs()` — all filters (image, run, card, composed), results/ exclusion, empty/missing docker/, card_dirs population (`test_harvest_validated_results.py`)
- `discover_validated_runs(results_repo=)` / `harvest(results_repo=)` — harvest-equivalence: rows from the migrated results repo equal the legacy walk's byte-for-byte for a mixed modern/legacy/unreadable fixture; identical discovery order, card dirs and filter behavior; records without a `legacy-tree` pointer skipped; missing legacy location warned and skipped; `--results-repo` parsing and env fallback; `main()` source line (`test_harvest_results_repo.py`)
- `migrate_validated_results.py` — every legacy manifest shape (unpadded `card_filter`, older `cards` key without timeout, missing `benchmark_set`, Resume Leg, null-filter 271-card run, narrower filter, `workspace_final`-only, unknown benchmark, missing summary block); plan/skip separation; `--dry-run` writes nothing; apply writes records + index and is idempotent (byte-identical re-run); rerun conflicts (exact existing records skipped; empty, malformed, incomplete, or differing destinations become `MigrationConflict`s that abort the apply with nothing written); partial-apply recovery; source tree unmodified; usage error without a repo; env var selection; real-corpus expectations (82 → 79 records, 3 known skips, 77 valid / 2 invalid with notes, 1 Resume Leg, 4 `cards`-key manifests) (`test_migrate_validated_results.py`)
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

- `summarize_breadth()` — breadth = distinct failing images; pass/rollup don't count; duplicate failing image counted once; sorted failing_images; separate groups per tests_hash (`test_harvest_summary.py`)
- `summarize_breadth()` — tests_hash=None is a distinct group from string hashes; None sorts last in tiebreak (`test_harvest_summary.py`)
- `summarize_breadth()` — ranking descending by breadth with deterministic tiebreak on (card, test_node, tests_hash) (`test_harvest_summary.py`)
- `summarize_breadth()` — rollup-only group has breadth 0 and is included (`test_harvest_summary.py`)
- `summarize_breadth()` — empty rows list returns [] without crash (`test_harvest_summary_gaps.py`)
- `summarize_breadth()` — row missing 'outcome' key tolerated (not counted as fail) (`test_harvest_summary_gaps.py`)
- `summarize_breadth()` — failing_images sorted lexicographically regardless of input arrival order (`test_harvest_summary_gaps.py`)
- `load_rows()` — round-trip JSONL with and without blank lines; empty file returns [] (`test_harvest_summary.py`)
- `write_summary()` — creates parent dirs, writes pretty-printed JSON, file round-trips, newline-terminated, empty list valid (`test_harvest_summary.py`, `test_harvest_summary_gaps.py`)
- `main(--summary)` — loads JSONL, writes harvested_summary.json sibling, prints ranked report, missing JSONL → non-zero exit + stderr (`test_harvest_summary.py`)
- `main(--summary)` — JSONL of only rollup rows → all groups breadth 0 in written JSON (`test_harvest_summary_gaps.py`)

- `mine_candidates()` — novel behavior surfaced, name-match suppressed, API-overlap rule (both conditions), missing audited file, card filter, SyntaxError robustness, provenance (`test_mine_promotion_candidates.py`)
- `mine_candidates()` — empty agent tests.py (no test fns) yields zero candidates without crashing (`test_mine_promotion_candidates_gaps.py`)
- `mine_candidates()` — empty engine API Jaccard edge: _jaccard({},{})=0.0, no ZeroDivisionError, Rule 2 does not wrongly suppress (`test_mine_promotion_candidates_gaps.py`)
- `mine_candidates()` — class-based test methods inside `class TestX:` detected end-to-end, and suppressed by name match (`test_mine_promotion_candidates_gaps.py`)
- `mine_candidates()` — audited-only tests (not written by agent) produce no spurious candidates; agent subset fully covered by audited → zero candidates (`test_mine_promotion_candidates_gaps.py`)
- `format_candidates_json()` — output is valid JSON with ALL Candidate dataclass fields present and correct values; direct `format_candidates_json` call and CLI `--format json` path (`test_mine_promotion_candidates_gaps.py`)
- `is_behavior_covered()` — unit: name match, no-match, empty audited, empty-API both sides (`test_mine_promotion_candidates.py`, `test_mine_promotion_candidates_gaps.py`)
- `extract_test_behaviors()` — async, class methods, non-test functions ignored, engine API extraction, class-based integration (`test_mine_promotion_candidates.py`, `test_mine_promotion_candidates_gaps.py`)
- `_normalize_test_name()` — prefix strip, suffix strip, lowercase (`test_mine_promotion_candidates.py`)
- `main()` — text output, JSON output, never-promotes, no-candidates text (`test_mine_promotion_candidates.py`)

- `check_canonical_api()` — unparseable candidate (SyntaxError) returns fail-closed with reason mentioning parse failure and file path (`test_check_promotion_candidate_gaps.py`)
- `check_canonical_api()` — both engine dirs missing: no oracle-only symbols, candidate passes (`test_check_promotion_candidate_gaps.py`)
- `check_canonical_api()` — canonical dir missing, oracle has symbols: oracle-only symbols exist, candidate referencing them is rejected (`test_check_promotion_candidate_gaps.py`)
- `check_canonical_api()` — oracle dir missing, canonical has symbols: no oracle-only symbols, candidate passes (`test_check_promotion_candidate_gaps.py`)
- `check_promotion_candidate()` — canonical-API fail + oracle pass → `allowed=False`; all three checks still run and present in result (`test_check_promotion_candidate_gaps.py`)
- `main()` — ADR-011 maintainer note printed to stderr regardless of outcome (`test_check_promotion_candidate_gaps.py`)
- `main()` — failing check name, FAIL label, and reason symbol appear in stdout (`test_check_promotion_candidate_gaps.py`)
- `main()` — REJECTED verdict printed to stdout when any check fails (`test_check_promotion_candidate_gaps.py`)
- `main()` — exit code == 1 (non-zero) when only canonical-API check fails (tier=pass, oracle=pass) (`test_check_promotion_candidate_gaps.py`)
- `main()` — exit code == 1 (non-zero) when only oracle check fails (tier=pass, canonical=pass) (`test_check_promotion_candidate_gaps.py`)

## 2. Gaps (Not Yet Covered)

None — all identified gaps for items 4, 5, 6, 8, and 9 are now covered.

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
- [x] summarize_breadth([]) → [] (no crash)
- [x] Row with missing 'outcome' key tolerated, not counted as fail
- [x] failing_images sorted lexicographically (not in input order)
- [x] write_summary output is newline-terminated valid JSON
- [x] --summary over rollup-only JSONL → all breadth-0 groups
