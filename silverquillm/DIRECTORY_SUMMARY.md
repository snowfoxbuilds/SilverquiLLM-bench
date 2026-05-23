# Directory Summary — `silverquillm/`

## Purpose

Core Python package for the SilverquiLLM benchmark runner. Provides CLI entry points for Docker-based agent evaluation runs, card spec generation, workspace staging, container lifecycle management, test evaluation, and result aggregation. Set-agnostic — individual benchmark card sets live under `benchmarks/{set_code}/`.

## Key Files

| File | Lines | Responsibility | Key Exports |
|------|-------|---------------|-------------|
| `__init__.py` | 9 | Package init. Declares `__all__` (empty). | — |
| `cli.py` | 403 | **CLI entry point** — Click commands `run` and `smoke` for Docker-based agent runs. Handles workspace staging, `ContainerLifecycle` invocation, result harvesting, card status writing, evaluation, and summary generation. | `main` |
| `runner.py` | 238 | **Container lifecycle management** — `ContainerLifecycle` class with pipe-reader + poll-loop architecture. Dedicated threads drain Docker stdout/stderr to host files; main thread polls on ~1s interval for live streaming, timeout enforcement, and snapshot callbacks. | `ContainerLifecycle`, `LifecycleResult` |
| `workspace.py` | 209 | **Workspace staging** — Builds the workspace directory mounted into Docker containers. Copies engine, cards (with optional `card_filter`), reference docs, and prompt.md. Collector-number filtering with zero-pad normalization. | `stage_workspace` |
| `card_loader.py` | 352 | **Card loading** — Loads card specs from JSON, filters by collector number or prototype list, sorts by complexity tier. Template detection. | `load_all_card_specs`, `load_card_spec`, `load_card_impl`, `is_template`, `filter_by_collectors` |
| `card_spec.py` | 239 | **Card spec generation** — Converts Scryfall card data to card specs with class name derivation, base class determination, and metadata extraction. | `generate_card_spec`, `generate_all_specs`, `card_name_to_class_name` |
| `evaluator.py` | 952 | **Test evaluation** — Runs pytest against agent card implementations, parses results, supports self-eval, cross-eval, audited eval, and full evaluation with engine extension checks. | `evaluate`, `run_self_eval`, `run_audited_eval`, `EvalResult`, `FullEvalResult` |
| `results.py` | 359 | **Result aggregation** — Generates run summaries with pass/fail counts, engine churn metrics, and natural-sorted card results. | `generate_run_summary` |

## Subdirectories

- **`replay/`** — 17lands GRE replay parser, executor, and divergence detection pipeline. See `silverquillm/replay/DIRECTORY_SUMMARY.md`.

## Architecture & Patterns

- **`_REPO_ROOT` convention**: Both `cli.py` and `workspace.py` define `_REPO_ROOT = Path(__file__).resolve().parent.parent` for repo-relative path resolution. Cards and engine directories are constants, not configurable.
- **Per-image results path**: Results are stored under `docker/<image_dir>/results/<run_name>/`. Three helpers in `cli.py` manage this:
  - `_image_dir(image)` — strips `silverquillm-` prefix and `:tag` suffix from Docker image names.
  - `_image_results_dir(image)` — returns `_REPO_ROOT / "docker" / _image_dir(image) / "results"`.
  - `_make_run_name(set_code="sos")` — generates `<set_code>_<YYYY-MM-DDThh-mm>` run names.
- **Container lifecycle**: `ContainerLifecycle` (in `runner.py`) replaces raw `subprocess.run` calls. Two pipe-reader threads drain stdout/stderr to `.tmp` files, then copy to `.log` files after threads join. The main thread polls for timeouts (hard + hang) and snapshot callbacks.
- **Card filtering**: `--cards` CLI option accepts comma-separated collector numbers with zero-pad normalization (`str(int(x))`). Filtering happens at workspace staging time.
- **Run manifest**: `cli.py` writes `run_manifest.json` (timeout_seconds + deadline_utc) after staging.
- **Result harvesting**: `_harvest_results` copies output files, timeout reason, engine diff, and workspace final state from the Docker output directory into the run results directory.

## Developer Guide

- **Entry point**: `pyproject.toml` registers `benchmark = "silverquillm.cli:main"`.
- **Adding commands**: Add new Click commands under `main` group in `cli.py`.
- **Testing**: Tests in `tests/test_cli_docker.py`, `tests/test_workspace.py`, `tests/test_runner.py`, `tests/test_cli_lifecycle_integration.py`.
