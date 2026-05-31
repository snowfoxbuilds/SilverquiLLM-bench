# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Spec deviation: Item 2 — per-node outcome capture mechanism
- **TODO spec expected**: Add `--report-log=<tmp>/report.jsonl` to the pytest invocation (described as "pytest's built-in machine-readable JSONL") and parse the `TestReport` entries.
- **Actual codebase state**: `--report-log` is provided by the `pytest-reportlog` plugin, which is NOT installed in this environment. Using it would require adding a new third-party dependency.
- **What was implemented instead**: An inline `conftest.py` is written into the test file's parent dir (already a temp dir in the SOS eval path) before pytest runs. It uses `pytest_runtest_logreport` (`when=="call"` for pass/fail, `when=="setup"`+`failed` for setup errors) and `pytest_collectreport` (`failed` for collection errors) to write a JSONL of `{"test_node","outcome"}` rows, then parses it into `CardResult.test_nodes`. If an audited-tests `conftest.py` already exists, the hooks are prepended and the original restored afterward. A `capture_test_nodes=False` optional param on `_run_pytest_with_pythonpath` keeps the existing 4-tuple return for all other callers (`_eval_fdn_cards`, `_eval_engine`); only `_eval_sos_cards` opts into the 5-tuple. Counts/`errors` still come from the unchanged `_parse_pytest_output`.
- **Impact**: `silverquillm/evaluator.py`. Establishes the per-node capture convention (no new dependency). Candidate for KEY_DECISIONS.

