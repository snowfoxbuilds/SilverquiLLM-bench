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

## Item 6: Cross-impl breadth summary view (--summary)

### Implementation
- `scripts/harvest_validated_results.py` — Added load_rows(), summarize_breadth(), write_summary(), _print_breadth_report() functions and --summary CLI flag with summary-mode logic in main()

### Tests
- `tests/test_harvest_summary.py` — 24 test cases: breadth = distinct failing images (dedup, pass exclusion), different tests_hash = separate groups, None vs real hash separation, descending ranking with tie-break determinism (card/test_node/None-last), rollup exclusion from breadth, pass-only groups included at breadth 0, load_rows round-trip with blank lines, CLI --summary integration (JSON sibling creation, ranked content, stdout report), missing JSONL non-zero exit, write_summary round-trip

## Item 7: Author .claude/skills/test-investigation/SKILL.md

### Implementation
- `.claude/skills/test-investigation/SKILL.md` — New Claude Code native skill documenting combined investigation/discovery modes for the manual v1 Test Harvester

### Tests
- `tests/test_test_investigation_skill.py` — 21 structural tests verifying SKILL.md frontmatter (name, description, allowed-tools), dataset path reference, Released-tier refusal rule, both Investigation/Discovery modes documented, human-reviewable output constraints, and audited tests path references

## Item 8: Discovery-candidate miner (scripts/mine_promotion_candidates.py)

### Implementation
- `scripts/mine_promotion_candidates.py` — New script that scans agent-written tests in validated results and surfaces novel behaviors not covered by the canonical audited suite, using AST-based heuristic (name match + API-overlap fallback)

### Tests
- `tests/test_mine_promotion_candidates.py` — 30 test cases: novel behavior surfacing, name-match suppression (Rule 1), API-overlap + docstring keyword suppression (Rule 2 both-conditions-required), missing audited file note, --card filter, SyntaxError robustness, per-run provenance, CLI text/json output and never-promotes invariant, normalize-name and extract-behaviors unit tests

## Item 9: Discovery→promotion bar gate (scripts/check_promotion_candidate.py)

### Implementation
- `scripts/check_promotion_candidate.py` — New promotion bar gate script with check_tier, check_canonical_api, check_oracle_gate, and check_promotion_candidate orchestrator
- `benchmarks/sos/config.json` — Created with tier=benchmarking (required by tier check and item 7 skill)

### Tests
- `tests/test_check_promotion_candidate.py` — 31 test cases: allowed path (all checks pass + exit 0), oracle reject (fail + exit non-zero), released-tier refusal with short-circuit (oracle never called), check_tier unit tests (beta/benchmarking/released/missing/invalid), check_canonical_api real AST tests (canonical-only ok, oracle-only rejected with symbol named, stdlib-only ok), fail-closed oracle gate (missing card, subprocess error), never-promotes invariant (no audited files modified), real config.json validation, dataclass structure
