# Directory Summary — `silverquillm/`

## Purpose

Core Python package for the SilverquiLLM benchmark runner. Provides CLI entry points for Docker-based agent evaluation runs, card spec generation, workspace staging, container lifecycle management, telemetry, live log viewing, test evaluation, and result aggregation. Set-agnostic — individual benchmark card sets live under `benchmarks/{set_code}/`.

## Key Files

| File | Lines | Responsibility | Key Exports |
|------|-------|---------------|-------------|
| `__init__.py` | 9 | Package init. Declares `__all__` (empty). | — |
| `cli.py` | ~450 | **CLI entry point** — Click commands `run` and `smoke` for Docker-based agent runs. Handles workspace staging, `ContainerLifecycle` invocation, snapshot callback wiring, `_runner_log()` file logging, result harvesting (skips docker_stdout/stderr if already streamed), card status writing, evaluation, and summary generation. | `main` |
| `runner.py` | ~240 | **Container lifecycle management** — `ContainerLifecycle` class with pipe-reader + poll-loop architecture. Dedicated threads drain Docker stdout/stderr directly to run_dir log files via `_drain_pipe` (TextIOWrapper, line-by-line UTF-8 streaming). Main thread polls on ~1s interval for timeout enforcement and snapshot callbacks. | `ContainerLifecycle`, `LifecycleResult` |
| `workspace.py` | ~50 | **Workspace staging** — Four-step copytree form: copies `benchmarks/sos/workspace/` to run workspace, applies per-run overlays (prompt.md, card_filter), and runs pre-flight checks. | `stage_workspace` |
| `telemetry.py` | ~200 | **Fast telemetry** — `FastTelemetry` class that polls mtime changes on telemetry channel files (system.log, agent_stdout.log, snapshot_telemetry.jsonl, etc.) and fires callbacks. Emits bootstrap JSON line on first poll pass. No progress.jsonl channel. | `FastTelemetry`, `CHANNEL_FILES` |
| `logs_viewer.py` | ~180 | **Live log viewer** — Rich-based TUI for tailing telemetry channels during runs. Tabs per channel with visibility polling (structurally-empty channels hidden, rediscovered on 2s poll). | `LogsViewer` |
| `card_loader.py` | 352 | **Card loading** — Loads card specs from JSON, filters by collector number or prototype list, sorts by complexity tier. Template detection. | `load_all_card_specs`, `load_card_spec`, `load_card_impl`, `is_template`, `filter_by_collectors` |
| `card_spec.py` | 239 | **Card spec generation** — Converts Scryfall card data to card specs with class name derivation, base class determination, and metadata extraction. | `generate_card_spec`, `generate_all_specs`, `card_name_to_class_name` |
| `card_names.py` | ~50 | **Card name utilities** — Helpers for card name resolution and mapping. | — |
| `evaluator.py` | ~960 | **Test evaluation** — Runs pytest against agent card implementations, parses results, supports self-eval, cross-eval, audited eval, and full evaluation with engine extension checks. Audited tests at `benchmarks/sos/data/tests/audited/`. `CardResult` includes `tests_hash: str` (SHA-256 of audited test file) and `test_nodes: list[dict]` (per-test-node pass/fail outcomes captured via an inline conftest injected by `_run_pytest_with_pythonpath` when `capture_test_nodes=True`; populated in `_eval_sos_cards`). JSONL report parsed by `_parse_report_jsonl`; nodeids are normalized before storage. | `evaluate`, `run_self_eval`, `run_audited_eval`, `EvalResult`, `FullEvalResult`, `CardResult` |
| `results.py` | 359 | **Result aggregation** — Generates run summaries with pass/fail counts, engine churn metrics, and natural-sorted card results. | `generate_run_summary` |

## Subdirectories

- **`replay/`** — 17lands GRE replay parser, executor, and divergence detection pipeline. See `silverquillm/replay/DIRECTORY_SUMMARY.md`.

## Architecture & Patterns

- **`_REPO_ROOT` convention**: Both `cli.py` and `workspace.py` define `_REPO_ROOT = Path(__file__).resolve().parent.parent` for repo-relative path resolution.
- **Workspace as copytree**: `stage_workspace()` copies `benchmarks/sos/workspace/` as a single `shutil.copytree` call, then applies per-run overlays. No per-file staging helpers.
- **Per-image results path**: Results are stored under `docker/<image_dir>/results/<run_name>/`. Three helpers in `cli.py` manage this:
  - `_image_dir(image)` — strips `silverquillm-` prefix and `:tag` suffix from Docker image names.
  - `_image_results_dir(image)` — returns `_REPO_ROOT / "docker" / _image_dir(image) / "results"`.
  - `_make_run_name(set_code="sos")` — generates `<set_code>_<YYYY-MM-DDThh-mm>` run names.
- **Container lifecycle**: `ContainerLifecycle` (in `runner.py`) uses two pipe-reader threads that stream Docker stdout/stderr directly to `.log` files in `run_dir` (no `.tmp` intermediate). Main thread polls for timeouts (hard + hang) and snapshot callbacks.
- **Direct-write docker logs**: `docker_stdout.log` and `docker_stderr.log` are written directly during the run (not post-exit copy). `_harvest_results` skips them if already present.
- **Snapshot callback**: `_snapshot_callback` closure in `cli.py` writes `snapshot_telemetry.jsonl` and optionally calls `_display.emit_snapshot()`.
- **Runner logging**: `_runner_log()` helper writes ISO-8601 timestamped lines to `runner.log` and errors to `runner_errors.log`.
- **Card filtering**: `--cards` CLI option accepts comma-separated collector numbers with zero-pad normalization (`str(int(x))`). Filtering happens at workspace staging time.
- **Run manifest**: `cli.py` writes `run_manifest.json` (timeout_seconds + deadline_utc) after staging.
- **No progress.jsonl**: The progress channel has been removed from telemetry, logs viewer, runner, and entrypoints.

## Developer Guide

- **Entry point**: `pyproject.toml` registers `benchmark = "silverquillm.cli:main"`.
- **Adding commands**: Add new Click commands under `main` group in `cli.py`.
- **Testing**: Tests in `tests/test_cli_docker.py`, `tests/test_workspace.py`, `tests/test_runner.py`, `tests/test_cli_lifecycle_integration.py`, `tests/test_snapshot_callback.py`, `tests/test_docker_direct_stream.py`, `tests/test_telemetry.py`, `tests/test_logs_viewer.py`, `tests/test_runner_log.py`.
