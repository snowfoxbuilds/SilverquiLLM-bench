# Directory Summary — `silverquillm/`

## Purpose

Set-agnostic benchmark runner package for evaluating LLM coding capabilities on MTG card implementations. Contains the full pipeline: card classification → spec generation → template generation → prompt assembly → agent session management (with pluggable adapters) → evaluation → scoring → result recording. Individual benchmark data sets live under `benchmarks/{set_code}/`.

Renamed from `benchmark/` to `silverquillm/` during this run.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package docstring; marks `silverquillm/` as a Python package. |
| `config.py` | **Config loader** — `BenchmarkConfig` and nested `AgentConfig` dataclasses; `load_config()` for YAML validation. `AgentConfig` holds adapter name, timeout, max rounds, and feature flags. |
| `cli.py` | **CLI entry point** — Click-based CLI with `run`, `eval`, `score`, `cards`, `validate` subcommands. Full orchestration loop with `--cards`, `--prototype`, `--dry-run` flags. Cards sorted by complexity tier. Wires persistent engine lifecycle. `validate` subcommand delegates to `silverquillm.replay.cli`. Entry point: `benchmark` (pyproject.toml). |
| `agent_session.py` | **Agent session manager** — `AgentSession` dataclass managing workspace setup, adapter lifecycle, and the two-phase implementation flow (blind → test-informed) with contamination controls. Postmortem JSONL logging and `agent_thoughts.md` narrative generation. Persistent engine support via `init_run_engine`, `commit_engine_changes`, `save_engine_final`, `compute_engine_diff`. |
| `card_classifier.py` | **Complexity classifier** — Heuristic-based tier assignment (trivial/simple/medium/complex/advanced). Outputs both `tier` and `complexity_tier` keys. |
| `card_spec.py` | **Spec generator** — `generate_card_spec()` and `generate_all_specs()` produce per-card JSON spec files with oracle data + complexity tier. |
| `card_loader.py` | **Card-spec loading & filtering** — `load_card_specs()`, `load_prototype_cards()`, `filter_by_collectors()`, `filter_by_prototype()`. |
| `template_gen.py` | **Template generator** — `card_name_to_class_name()`, `resolve_base_class()`, `compile_template()` / `render_template()` for card stubs. |
| `docs_gen.py` | **Engine API doc generator** — AST-based extraction from `engine/` producing `docs/engine_api.md` (~5,000 token budget). |
| `rules_skill.py` | **Rules indexer** — Downloads, parses, indexes MTG comprehensive rules; provides keyword/section lookup. |
| `prompts.py` | **Prompt templates** — `blind_prompt()`, `test_informed_prompt()`, `iteration_feedback_prompt()` with engine extensibility instructions. Uses `str.format_map`. |
| `evaluator.py` | **Evaluation runner** — `EvalResult`, `run_tests()` (subprocess pytest), `run_self_eval()`, `run_cross_eval()`, `run_audited_eval()`. |
| `scorer.py` | **Scoring calculator** — 4-category scoring: Blind, Tested, Audited, Engine Extension Quality. `Leaderboard` dataclass, `generate_leaderboard()`. |
| `results.py` | **Result recorder** — Per-run directory isolation. `generate_run_name()`, `init_results_dir()`, `save_card_result()`, `save_run_summary()`, `save_aggregates()` with category4. |
| `run_utils.py` | **Run orchestration helpers** — `_session_results_to_dicts()` for converting session results to dicts. |
| `prototype.py` | **Prototype selection** — Scoring-based card selection (one per complexity tier) plus engine gap analysis. |
| `regression.py` | **Regression test runner** — Re-runs completed cards' tests after each card. `run_regressions()`, `regression_feedback_prompt()`. |
| `setup_questions.py` | **Setup questions validation** — Loads setup questions JSON and validates adapter responses. |

## Subdirectories

- **`adapters/`** — Pluggable agent adapter system. See `silverquillm/adapters/DIRECTORY_SUMMARY.md`.
- **`replay/`** — 17lands GRE replay parser, executor, and validation pipeline. See `silverquillm/replay/DIRECTORY_SUMMARY.md`.

## Module Dependency Graph

```
config.py  (standalone — YAML loading, AgentConfig)
    ↑
adapters/base.py  (imports config.BenchmarkConfig)
    ↑
adapters/{opencode,claude_code,aider,pi}.py  (concrete adapters)
    ↑
agent_session.py  (uses adapters, prompts, template_gen, config)
    ↑
run_utils.py  (imports agent_session dataclasses, config)

template_gen.py  (no internal deps)
    ↑
prompts.py  (imports card_name_to_class_name from template_gen)

card_classifier.py → card_spec.py → prototype.py

docs_gen.py     (reads engine/ via AST)
rules_skill.py  (standalone)
setup_questions.py  (uses adapters)
regression.py  (subprocess pytest for cross-card validation)

cli.py  (top-level orchestrator — imports most modules)
evaluator.py → scorer.py → results.py
```

## Important Conventions

- **Adapter system**: All agent interaction goes through `AgentAdapter` subclasses. Use `get_adapter(config)` factory.
- **Nested config**: Agent settings live under `config.agent` (`AgentConfig` dataclass).
- **Tier naming**: Both `tier` and `complexity_tier` keys supported; prefer `complexity_tier`.
- **Prompt templates** use `str.format_map` with `{placeholder}` — no f-strings with logic.
- **Persistent engine**: Engine directory writable and persists across cards; diffs captured per-card.
- **Postmortem logging**: JSONL logging per agent run; `agent_thoughts.md` generated post-run.
- **Subprocess isolation**: Evaluation runs pytest in subprocesses.
- **Results** written to per-run directories under `benchmarks/sos/results/`.
