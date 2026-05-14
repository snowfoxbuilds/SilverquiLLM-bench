# Directory Summary — `silverquillm/`

## Purpose

Host-side benchmark runner package for the SilverquiLLM benchmark. Stages workspaces, launches Docker containers, harvests results, evaluates card implementations, and generates run summaries. Registered CLI entry point: `benchmark = "silverquillm.cli:main"`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `__init__.py` | ~1 | Package init. |
| `cli.py` | 610 | **CLI entry point** — Click-based commands: `run` (full benchmark), `smoke` (quick test), `logs` (colorized log viewer). `run`/`smoke` use `subprocess.Popen` with explicit `docker stop` on timeout/interrupt via `_stop_container()`. Supports `--cards` filter, `--cards-dir`, `--engine-dir` options. `format_log_lines()` for multi-channel log interleaving with color-coded channels. `_harvest_results()` copies all `.log` files. `_generate_run_summary()` writes `card_filter` to `run_summary.json`. |
| `workspace.py` | 205 | **Workspace staging** — `stage_workspace()` builds the workspace directory mounted into Docker containers. Supports `card_filter` parameter for subset runs with `_PROMPT_ALL`/`_PROMPT_SUBSET` prompt templates. |
| `card_loader.py` | 352 | **Card spec loading** — `load_all_card_specs()`, `is_template()` for detecting unfilled card stubs. |
| `card_spec.py` | 239 | **Card spec generation** — Scryfall data → per-card `card_spec.json` files. |
| `evaluator.py` | 952 | **Post-harvest evaluator** — Runs pytest across three evaluation dimensions (SOS correctness, FDN regression, engine regression). |
| `results.py` | 359 | **Run summary generation** — `run_summary.json` creation, run naming, directory initialization. |

## Important Classes / Functions

- **`stage_workspace()`** — Builds workspace + output directories for Docker container mounting. Accepts `card_filter` for subset runs.
- **`main()`** — Click group entry point registering `run`, `smoke`, and `logs` commands.
- **`run()`** — Full benchmark run: workspace staging → Docker launch → timeout management → result harvesting → evaluation.
- **`smoke()`** — Quick smoke test variant of `run()`.
- **`_stop_container()`** — Explicit `docker stop` for container cleanup on timeout or KeyboardInterrupt.
- **`format_log_lines()`** — Multi-channel log interleaving with color-coded output (stdout/stderr/agent channels).
- **`_harvest_results()`** — Copies results and `.log` files from Docker output volume.

## Subdirectories

- **`replay/`** — 17lands GRE replay parser, executor, and validation pipeline. See `silverquillm/replay/DIRECTORY_SUMMARY.md`.

## Dependencies

- **`cards/`** — Card specs and registry for workspace staging.
- **`engine/`** — Game engine (evaluated inside Docker containers).
- **External**: `click` (CLI framework), `subprocess` (Docker invocation), `shutil`/`tempfile` (workspace staging).

## Testing

- `tests/test_card_filter.py` — Card filter workspace staging, prompt content, CLI option parsing.
- `tests/test_multichannel_output.py` — Log harvesting, format_log_lines, logs CLI command.
- `tests/test_container_timeout.py` — Popen-based timeout, docker stop, container naming.
- `tests/test_smoke_integration.py` — Integration tests for full smoke test and container lifecycle.
- `tests/test_workspace.py` — Workspace staging unit tests.
- `tests/test_cli_docker.py` — Docker CLI flag tests.
