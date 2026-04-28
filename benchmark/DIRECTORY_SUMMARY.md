# Directory Summary — `benchmark/`

## Purpose

Set-agnostic benchmark runner package for evaluating LLM coding capabilities on MTG card implementations. Contains the full pipeline: card classification → spec generation → template generation → prompt assembly → agent session management → evaluation → scoring → result recording. Individual benchmark data sets live under `benchmarks/{set_code}/`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `__init__.py` | 9 | Package docstring; marks `benchmark/` as a Python package. |
| `card_classifier.py` | 269 | **Complexity classifier** — Heuristic-based tier assignment (trivial/simple/medium/complex/advanced) using oracle text, keywords, and card types. Targeting bumps cards to at least medium. |
| `card_spec.py` | 158 | **Spec generator** — `generate_card_spec()` and `generate_all_specs()` produce per-card JSON spec files with oracle data + complexity tier for agent context. |
| `template_gen.py` | 155 | **Template generator** — `card_name_to_class_name()` (PascalCase with word-boundary fix), `resolve_base_class()` (card type → engine base class), `compile_template()` / `render_template()` for card stubs. Ambiguous multi-type falls back to `CardImpl`. |
| `docs_gen.py` | 230 | **Engine API doc generator** — AST-based extraction of public classes, enums, functions from `engine/`. Produces `docs/engine_api.md` within a ~5,000 token budget. |
| `rules_skill.py` | 650 | **Rules indexer** — Downloads MTG comprehensive rules, parses/indexes them, provides keyword/section lookup, and generates `rules_overview.md` (~573 tokens). |
| `prompts.py` | 170 | **Prompt templates** — `blind_prompt()`, `test_informed_prompt()`, `iteration_feedback_prompt()` using `str.format_map` with `{placeholder}` substitution. Imports `card_name_to_class_name` from `template_gen`. |
| `agent_session.py` | 660 | **Agent session manager** — `AgentSession` dataclass managing workspace setup, OpenCode config, blind phase and test-informed phase execution with max-round limits. `BlindResult` / `TestInformedResult` dataclasses. |
| `config.py` | 79 | **Config loader** — `BenchmarkConfig` dataclass and `load_config()` for YAML validation. |
| `cli.py` | 81 | **CLI entry point** — Click-based CLI with `run`, `eval`, `score`, `cards` subcommands. Entry point: `benchmark` (pyproject.toml `[project.scripts]`). |
| `evaluator.py` | 325 | **Evaluation runner** — `EvalResult` dataclass, `run_tests()` (subprocess pytest isolation), `run_self_eval()`, `run_cross_eval()`, `run_audited_eval()`. |
| `scorer.py` | 465 | **Scoring calculator** — `Leaderboard` dataclass, `compute_scores()` (3-category metrics from EvalResults), `generate_leaderboard()` (Markdown tables). |
| `results.py` | 513 | **Result recorder** — `generate_run_name()`, `init_results_dir()`, `save_card_result()`, `save_run_summary()`, `save_aggregates()`. Per-run directory isolation. |
| `prototype.py` | 391 | **Prototype selection** — Scoring-based card selection (one per complexity tier) from SOS set, plus engine gap analysis output. |

## Module Dependency Graph

```
template_gen.py  (no internal deps)
    ↑
prompts.py  (imports card_name_to_class_name from template_gen)

card_classifier.py  (no internal deps)
    ↑
card_spec.py  (uses classifier tiers)
    ↑
prototype.py  (uses classifier + card_spec data)

docs_gen.py     (reads engine/ source via AST — no runtime imports)
rules_skill.py  (standalone — downloads/parses rules text)

config.py  (standalone — YAML loading)
    ↑
cli.py  (imports config, orchestrates other modules)
    ↑
agent_session.py  (uses prompts, template_gen, config)
    ↑
evaluator.py  (subprocess pytest — no direct module imports at eval time)
    ↑
scorer.py  (consumes EvalResult dataclasses)
    ↑
results.py  (writes scored outputs to disk)
```

## Important Conventions

- **Prompt templates** use `str.format_map` with `{placeholder}` — no f-strings with logic.
- **Agent sessions** run in isolated workspace directories; engine path is exposed via OpenCode config.
- **Evaluation** uses subprocess pytest for isolation — implementations are never imported into the runner process.
- **Scoring** uses 3 categories (self-eval, cross-eval, audited-eval) with complexity-tier weighting.
- **Results** are written to per-run directories under `benchmarks/sos/results/` so runs never collide.
