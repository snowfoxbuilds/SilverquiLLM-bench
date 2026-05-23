# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Update _make_run_name(), add _image_dir() and _image_results_dir()

### Implementation
- `silverquillm/cli.py` — Added `_image_dir()` and `_image_results_dir()` helpers, updated `_make_run_name()` signature to `set_code="sos"`, wired `_image_results_dir(image)` as default in `run()`


## Item 2: Update .gitignore for new results path convention

### Implementation
- `.gitignore` — Replaced `results/` with `docker/*/results/` to ignore result artifacts under new path convention

## Item 3: Update README.md — all legacy results path references

### Implementation
- `README.md` — Replaced all `results/{run_name}/...` references with `docker/<image_dir>/results/<run_name>/...` and added `<image_dir>` derivation note

## Item 4: Update PROJECT_MAP.md — results path references

### Implementation
- `PROJECT_MAP.md` — Replaced `results/{run_name}/` with `docker/<image_dir>/results/<run_name>/` in overview paragraph and architecture diagram

## Item 5: Update runner specs — BENCHMARK-RUNNER.md, RUN-ARTIFACTS-AND-TELEMETRY.md, WORKSPACE-CONTRACT.md, AGENT-CONTAINERS.md

### Implementation
- `docs/specs/BENCHMARK-RUNNER.md` — Already contains new docker/<image-dir>/results/<run_name>/ paths (no changes needed)
- `docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md` — Already contains new docker/<image-dir>/results/<run_name>/ paths (no changes needed)
- `docs/specs/WORKSPACE-CONTRACT.md` — Already contains new docker/<image-dir>/results/<run_name>/ paths (no changes needed)
- `docs/specs/AGENT-CONTAINERS.md` — Already contains new docker/<image-dir>/results/<run_name>/ paths (no changes needed)

## Item 6: Update docs/specs/TEST-SUITE.md — results path and stale engine_work/ reference

### Implementation
- `docs/specs/TEST-SUITE.md` — Updated results path to docker/<image_dir>/results/<run_name>/cards/{card_id}/ and replaced engine_work/ with workspace_final/engine/

## Item 7: Update ADR-005, HELP.md, and KNOWN-ISSUES.md

### Implementation
- `docs/adrs/ADR-005: In-Place Workspace Engine With Snapshot Fallback.md` — Updated materialized path to `docker/<image_dir>/results/<run_name>/workspace_final/`
- `docs/HELP.md` — Updated git add example to use `docker/local-pi-blind/results/` path
- `docs/specs/KNOWN-ISSUES.md` — Added legacy-path parenthetical notes to historical `benchmarks/sos/results/` references

## Item 8: Update benchmarks/ directory summaries

### Implementation
- `benchmarks/DIRECTORY_SUMMARY.md` — Removed `results/` from convention pattern, added note pointing to `docker/<image_dir>/results/`
- `benchmarks/sos/DIRECTORY_SUMMARY.md` — Marked `results/` row as deprecated with note pointing to new location

## Item 9: Add test artifact cleanup and update TESTING-CONVENTIONS.md

### Implementation
- `tests/test_smoke_lifecycle.py` — Refactored to use smoke_image fixture with PID-tagged name and cleanup in teardown
- `docs/specs/TESTING-CONVENTIONS.md` — Added Rule 8 (no persistent artifacts) and Docker cleanup checklist item
