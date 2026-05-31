# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Spec deviation: Item 2 — per-node outcome capture mechanism
- **TODO spec expected**: Add `--report-log=<tmp>/report.jsonl` to the pytest invocation (described as "pytest's built-in machine-readable JSONL") and parse the `TestReport` entries.
- **Actual codebase state**: `--report-log` is provided by the `pytest-reportlog` plugin, which is NOT installed in this environment. Using it would require adding a new third-party dependency.
- **What was implemented instead**: An inline `conftest.py` is written into the test file's parent dir (already a temp dir in the SOS eval path) before pytest runs. It uses `pytest_runtest_logreport` (`when=="call"` for pass/fail, `when=="setup"`+`failed` for setup errors) and `pytest_collectreport` (`failed` for collection errors) to write a JSONL of `{"test_node","outcome"}` rows, then parses it into `CardResult.test_nodes`. If an audited-tests `conftest.py` already exists, the hooks are prepended and the original restored afterward. A `capture_test_nodes=False` optional param on `_run_pytest_with_pythonpath` keeps the existing 4-tuple return for all other callers (`_eval_fdn_cards`, `_eval_engine`); only `_eval_sos_cards` opts into the 5-tuple. Counts/`errors` still come from the unchanged `_parse_pytest_output`.
- **Impact**: `silverquillm/evaluator.py`. Establishes the per-node capture convention (no new dependency). Candidate for KEY_DECISIONS.

## Arbitration: Item 5 — keep `build_rows_for_run` returning `list[dict]`; legacy notice in `harvest()`
- **Context**: The Item 5 Implementer changed `build_rows_for_run`'s return type from `list[dict]` (the contract Item 4 established and Item 6 depends on) to `tuple[list[dict], bool]` to surface a per-run "is legacy" flag, and edited the Item 4 Tester's `tests/test_harvest_rows.py` to match — both outside its mandate (the Implementer must not modify Tester tests or break a committed public API without need).
- **Coordinator decision**: Revert. `build_rows_for_run` stays `-> list[dict]`. Per-run legacy detection moves into `harvest()`, which inspects each run's emitted rows for a rollup row (`row["test_node"] == "__rollup__"`) and prints the one-per-run `[legacy] <image>/<run>: ...` notice. The Implementer restores `tests/test_harvest_rows.py` to its committed state and touches only `scripts/harvest_validated_results.py`. The two Item-4 `TestMissingTestNodes` tests that encode the temporary "skip legacy cards" placeholder are then updated by the **Tester** (which owns test files) to the new skip→rollup behavior, alongside the new Item-5 legacy tests.
- **Reasoning**: Smaller blast radius, preserves the Item 4/6 API, and keeps the Implementer/Tester separation the skill mandates. Rollup rows are a reliable legacy marker, so no signature change is needed.
- **Impact**: `scripts/harvest_validated_results.py`, `tests/test_harvest_rows.py`.
- **Rollup row contract** (worth keeping): legacy cards emit one `test_node="__rollup__"` row with `outcome="rollup"` (a sentinel that is neither `pass` nor `fail`, so Item 6 breadth does not miscount it) carrying `passed`/`failed`/`total`; fail rows are derived from `errors` node ids; `tests_hash` is `null` for legacy cards.

