# Directory Summary — `silverquillm/`

## Purpose

Set-agnostic benchmark runner package for evaluating LLM coding capabilities on MTG card implementations. Contains the full pipeline: card classification → spec generation → template generation → prompt assembly → agent session management (with pluggable adapters) → evaluation → scoring → result recording. Individual benchmark data sets live under `benchmarks/{set_code}/`.

Renamed from `benchmark/` to `silverquillm/` during this run.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package docstring; marks `silverquillm/` as a Python package. |
| `config.py` | **Config loader** — `BenchmarkConfig` and nested `AgentConfig` dataclasses; `load_config()` for YAML validation. `AgentConfig` holds adapter name, timeout, max rounds, and feature flags. |
| `cli.py` | **CLI entry point** — Click-based CLI with `run`, `eval`, `score`, `cards`, `validate`, `aggregate` subcommands. Full orchestration loop with `--cards`, `--prototype`, `--dry-run`, `--skip-isolation-check` flags. Signal handler for graceful interrupt cleanup (`_active_session` tracking, `KeyboardInterrupt` handling, signal restoration in `try`/`finally`). Cards sorted by complexity tier. Wires persistent engine lifecycle. Calls `preflight_check()` before card loop, `run_post_eval()` after card loop, and `aggregate_run()` after post-eval. `--dry-run` uses MockAdapter for environment validation. `validate` subcommand delegates to `silverquillm.replay.cli`. Entry point: `benchmark` (pyproject.toml). |
| `agent_session.py` | **Agent session manager** — `AgentSession` dataclass with `card_id` field and `_path_id` property for standardized per-card path construction. Manages workspace setup, adapter lifecycle, and the two-phase implementation flow (blind → test-informed) with allowlist-based contamination controls. Uses `result.agent_output`/`result.prompt_used` from `CardRunResult` for postmortem logging and raw log capture. Postmortem JSONL logging with structured event helpers (`_append_file_written`, `_append_eval_result`, `_append_regression_check`) and `agent_thoughts.md` narrative generation. Persistent engine support via `init_run_engine`, `commit_engine_changes`, `save_engine_final`, `compute_engine_diff`. Contamination checker walks entire repo tree with allowlist (`_ALLOWED_DIRS`, `_IGNORED_SUFFIXES`). |
| `strategies.py` | **Card execution strategies** — `BlindStrategy` and `ImplTestStrategy` with hard timeout enforcement via direct `adapter.run_with_retries(timeout=timeout, retries=0)` calls (no ThreadPoolExecutor). `CardRunResult` dataclass includes `agent_output` and `prompt_used` fields. Calls `adapter.kill()` on timeout before raising `TimeoutError`. |
| `card_classifier.py` | **Complexity classifier** — Heuristic-based tier assignment (trivial/simple/medium/complex/advanced). Outputs both `tier` and `complexity_tier` keys. Includes `set_code` field in output. |
| `card_spec.py` | **Spec generator** — `generate_card_spec()` and `generate_all_specs()` produce per-card JSON spec files with oracle data + complexity tier. Composite key lookup for multi-set collision avoidance with set_code-prefixed output dirs. |
| `card_loader.py` | **Card-spec loading & filtering** — `load_card_specs()`, `load_prototype_cards()`, `filter_by_collectors()`, `filter_by_prototype()`. |
| `template_gen.py` | **Template generator** — `card_name_to_class_name()`, `resolve_base_class()`, `compile_template()` / `render_template()` for card stubs. Includes `GameState` in generated template imports. |
| `docs_gen.py` | **Engine API doc generator** — AST-based extraction from `engine/` producing `docs/engine_api.md` (~5,000 token budget). |
| `rules_skill.py` | **Rules indexer** — Downloads, parses, indexes MTG comprehensive rules; provides keyword/section lookup. Simplified to ~200 lines with minimal embedded fallback rules for offline use. |
| `prompts.py` | **Prompt templates** — `blind_prompt()`, `test_informed_prompt()`, `iteration_feedback_prompt()` with engine extensibility instructions. Uses `str.format_map`. |
| `evaluator.py` | **Evaluation runner** — `EvalResult`, `EvalResultV2` (mode-aware v2 schema), `run_tests()` (subprocess pytest with `engine_dir` parameter for PYTHONPATH), `run_self_eval()`, `run_cross_eval()`, `run_audited_eval()`. Supports `--audited-dir` for per-card audited test directories. |
| `scorer.py` | **Scoring calculator** — 4-category scoring: Blind, Tested, Audited, Engine Extension Quality. `Leaderboard` dataclass, `generate_leaderboard()`. Normalises v2 result records; `_v2_to_eval_dicts()` respects mode for blind/tested column selection. |
| `results.py` | **Result recorder** — Per-run directory isolation. `generate_run_name()`, `init_results_dir()`, `save_card_result()`, `save_card_result_v2()`, `load_card_result()`, `_normalise_to_v2()` (v1→v2 normalization with implementation flattening), `save_run_summary()`, `save_aggregates()` with category4. `iteration_count` excluded from impl metrics. |
| `run_utils.py` | **Run orchestration helpers** — `_session_results_to_dicts()` for converting session results to dicts. |
| `post_eval.py` | **Post-run evaluation** — `CardEvalResult` dataclass and `run_post_eval()` function. Runs all evaluation tests (self-eval and audited) against the final engine state after the card loop completes. Deterministic audited test lookup via `_resolve_audited_tests()`. Writes v2 schema result.json with `_merge_result_json()`. Wires `_append_eval_result` into postmortem logging. |
| `aggregator.py` | **Run-level aggregation** — `RunSummary` dataclass and `aggregate_run()` pure function. Aggregates per-card `result.json` files into a single `run_summary.json`. `save_run_summary_v2()` for persistence. Deterministic timestamp from result.json mtime, integer token handling, legacy status normalization. Idempotent. |
| `preflight.py` | **Pre-flight validation** — `preflight_check()` and `PreflightError`. Validates environment before LLM calls: card_specs_dir existence, config validity, workspace accessibility, template imports (including `GameState`), `test_utils` importability, engine test suite health, `.workspace/` directory, workspace isolation (canary UUID check). `skip_isolation_check` parameter to bypass isolation validation. Adapter/setup exceptions surface as preflight errors. |
| `prototype.py` | **Prototype selection** — Scoring-based card selection (one per complexity tier) plus engine gap analysis. |
| `regression.py` | **Regression test runner** — Re-runs completed cards' tests after each card. `run_regressions()`, `regression_feedback_prompt()`. |

## Subdirectories

- **`adapters/`** — Pluggable agent adapter system. See `silverquillm/adapters/DIRECTORY_SUMMARY.md`.
- **`replay/`** — 17lands GRE replay parser, executor, and validation pipeline. See `silverquillm/replay/DIRECTORY_SUMMARY.md`.

## Module Dependency Graph

```
config.py  (standalone — YAML loading, AgentConfig)
    ↑
adapters/base.py  (imports config.BenchmarkConfig, adds kill() support)
    ↑
adapters/{opencode,claude_code,aider,pi,mock}.py  (concrete adapters)
    ↑
strategies.py  (uses adapters — BlindStrategy, ImplTestStrategy with timeout enforcement)
    ↑
agent_session.py  (uses adapters, prompts, template_gen, config, strategies)
    ↑
run_utils.py  (imports agent_session dataclasses, config)

template_gen.py  (no internal deps, generates GameState import)
    ↑
prompts.py  (imports card_name_to_class_name from template_gen)

card_classifier.py → card_spec.py → prototype.py

docs_gen.py     (reads engine/ via AST)
rules_skill.py  (standalone)
regression.py  (subprocess pytest for cross-card validation)

preflight.py   (pre-run environment validation)
    ↑
cli.py  (top-level orchestrator — imports most modules, calls preflight → card loop → post_eval → aggregator)
    ↑
post_eval.py  (post-run evaluation — self-eval + audited eval)
    ↑
aggregator.py  (run-level result aggregation → run_summary.json)

evaluator.py → scorer.py → results.py
```

## Important Conventions

- **Adapter system**: All agent interaction goes through `AgentAdapter` subclasses. Use `get_adapter(config)` factory. Adapters implement `kill()` for hard timeout enforcement.
- **Mock adapter**: `MockAdapter` for deterministic testing; derives card_name from workspace card_spec.json.
- **Nested config**: Agent settings live under `config.agent` (`AgentConfig` dataclass).
- **Tier naming**: Both `tier` and `complexity_tier` keys supported; prefer `complexity_tier`.
- **Prompt templates** use `str.format_map` with `{placeholder}` — no f-strings with logic.
- **Persistent engine**: Engine directory writable and persists across cards; diffs captured per-card.
- **Postmortem logging**: JSONL logging per agent run with structured event helpers; `agent_thoughts.md` generated post-run.
- **Subprocess isolation**: Evaluation runs pytest in subprocesses.
- **Results** written to per-run directories under `benchmarks/sos/results/`.
- **V2 schema**: Result files use v2 schema with `schema_version` and `mode` fields; v1→v2 normalization supported.
- **Pre-flight validation**: `preflight_check()` runs before any LLM calls to catch misconfigurations early. Supports `skip_isolation_check` flag.
- **Post-run evaluation**: All evaluation (self-eval + audited) happens after the card loop via `run_post_eval()`.
- **Run aggregation**: `aggregate_run()` produces `run_summary.json` after post-eval; idempotent.
- **Signal handling**: Graceful interrupt cleanup via signal handler with `_active_session` tracking and signal restoration.
- **Card path construction**: `card_id` field and `_path_id` property on `AgentSession` standardize per-card directory naming.
- **Allowlist contamination**: Agent file access checked against allowlist (`engine/` allowed, `.pyc`/`.pyo`/`.log` ignored).
