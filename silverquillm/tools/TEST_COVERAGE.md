# Test Coverage — silverquillm/tools/

## 1. Covered

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

The harvest and miner coverage moved to the Results Repo with those scripts (`scripts/legacy/TEST_COVERAGE.md`, #222).
