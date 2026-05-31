# Test Coverage Map

| Directory | Status | Summary | Coverage File |
|-----------|--------|---------|---------------|
| `silverquillm/` | [Completed] | `tests_hash` and `test_nodes` features on `CardResult` fully covered; added 18 gap tests in `test_test_nodes_gaps.py` for skipped/xfail exclusion, unknown-outcome ignoring, `_normalize_nodeid` path-only branch, and cleanup guarantees. Also fixed an implementation bug where xfail outcomes were incorrectly captured as "fail". | [silverquillm/TEST_COVERAGE.md](silverquillm/TEST_COVERAGE.md) |
| `scripts/` | [Completed] | `harvest_validated_results.py`, `mine_promotion_candidates.py`, and `check_promotion_candidate.py` fully covered; added 12 gap tests in `test_check_promotion_candidate_gaps.py` for SyntaxError fail-closed, missing engine dirs, canonical-fail+oracle-pass aggregation, ADR-011 note on stderr, per-check reason in stdout, and single-check-failure exit codes. | [scripts/TEST_COVERAGE.md](scripts/TEST_COVERAGE.md) |
| `.claude/skills/test-investigation/` | [Skipped] | Documentation-only deliverable (SKILL.md). No executable production code. The Tester's `tests/test_test_investigation_skill.py` covers frontmatter, both modes, Released-tier refusal, dataset path, and human-reviewable-output rules. No additional tests warranted. | N/A |
