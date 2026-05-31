# Key Decisions

Persistent architectural and convention decisions across runs. Periodically drained into specs/ADRs

## Per-card SOS `result.json` schema for the Harvest workflow (Phase 19, items 1–2)
- **Context**: The test-improvement harvest (items 3–6) needs per-test-node outcomes and a way to detect audited-test changes across runs.
- **Decision**: `CardResult` (in `silverquillm/evaluator.py`), serialized via `asdict` into each `cards/<card>/result.json`, now carries two ADDITIVE fields:
  - `tests_hash: str` — SHA-256 hex digest of the audited `tests.py` bytes (`""` when the file is absent/unreadable).
  - `test_nodes: list[dict]` — one `{"test_node": "tests.py::test_x", "outcome": "pass"|"fail"}` per executed node, captured via an inline `conftest.py` written into the temp test dir (the `pytest-reportlog` plugin is NOT installed, so `--report-log` is unavailable). Per-node capture is **pass/fail-only by design**: skipped/xfail tests are intentionally NOT enumerated, so `len(test_nodes)` may be < `tests_total` when skips exist. Existing `tests_passed`/`tests_failed`/`tests_total`/`errors` come unchanged from `_parse_pytest_output`.
- **Reasoning**: Additive, no new dependency, keeps all existing eval behavior intact; downstream harvest rows (item 4) are one-per-node with `outcome ∈ {pass, fail}`.
- **Impact**: `silverquillm/evaluator.py`; the harvest script (items 3–6) reads these fields. Legacy Validated Results predating these fields lack them — item 5 handles back-compat (derive fail rows from `errors`, emit a `__rollup__` row, `tests_hash = null`).
