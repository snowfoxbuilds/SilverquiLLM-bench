# Directory Summary — `scripts/`

## Purpose

Standalone utility scripts for data pipeline tasks. Not part of the main package — run directly via `python scripts/<script>.py`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `build_card_id_map.py` | 230 | Fetches card data from Scryfall API and builds `data/replays/card_id_map.json`. Creates `grpId_to_card_name` forward map and `card_name_to_grpIds` reverse map (list-valued for duplicate-name disambiguation). Adds synthetic entries for SPG #74–83 (grpIds 94700–94709) flagged with `"synthetic": true`. Includes error handling for curl/Scryfall API failures. |
| `generate_audited_stubs.py` | ~200 | Reads `benchmarks/sos/data/sos.json` and generates `cards/stubs/sos_stubs.py` containing one stub class per card with colors, hybrid mana, planeswalker loyalty, Vehicle P/T, and `register_sos_stubs(registry)`. |
| `harvest_validated_results.py` | ~530 | **Phase 19 harvest pipeline — discovery, row emission, and summary analysis.** Discovers validated results by globbing `docker/*/validated_results/*/`. Exposes `discover_validated_runs(repo_root, *, image, run, card) -> list[ValidatedRun]` (sorted, filtered), `build_rows_for_run(vr, *, harvested_at) -> list[dict]` (one dict per `(card, test_node)` with keys `image, run, card, test_node, outcome, tests_hash, passed, failed, total, complexity_tier, harvested_at`), and `harvest(repo_root, *, bench, output, image, run, card, harvested_at) -> int` (full pipeline: discover → build rows → truncate-write JSONL → return row count). `main()` supports two modes: default harvest mode (delegates to `harvest()`) and **`--summary` mode** (delegates to `summarize_breadth(rows)`). **`--summary` mode** reusable API: `load_rows(path) -> list[dict]` reads a JSONL harvest file; `summarize_breadth(rows) -> list[dict]` groups rows by `(card, test_node, tests_hash)`, counts distinct failing images (cross-impl breadth), and returns records sorted descending by breadth; `write_summary(summary, path)` writes the result to `benchmarks/<bench>/analysis/harvested_summary.json`. Creates `benchmarks/<bench>/analysis/` on first run. **Legacy branch**: cards whose `result.json` lacks the `test_nodes` key (pre-items-1/2 results) are handled separately — `_extract_fail_nodes_from_errors(errors)` parses `FAILED`/`ERROR` lines from `result_data["errors"]` into normalized pytest node IDs; `build_rows_for_run` emits one `outcome="fail"` row per unique fail node plus one `outcome="rollup"` row for `test_node="__rollup__"` carrying pass/fail/total counts; `tests_hash` is `None` for all legacy rows. `harvest()` prints a one-per-run `[legacy] <image>/<run>` notice for any run that produced `__rollup__` rows. |

## Dependencies

- **External**: `requests` (HTTP), Scryfall API
- **Downstream**: `data/replays/card_id_map.json` consumed by `silverquillm/replay/parser.py` and `silverquillm/replay/executor.py`. `cards/stubs/sos_stubs.py` consumed by `tests/audited/sos/conftest.py`. `harvest_validated_results.py` writes to `benchmarks/<bench>/analysis/harvested_results.jsonl` (harvest mode) and `benchmarks/<bench>/analysis/harvested_summary.json` (summary mode).

| `mine_promotion_candidates.py` | ~530 | **Discovery-candidate miner.** AST-scans agent-written `tests.py` files in each Validated Results `cards/<card>/` subtree and surfaces behaviors not represented in the canonical audited suite (`benchmarks/<bench>/data/tests/audited/<bench>/<card>/tests.py`). Exposes `mine_candidates(repo_root, *, bench, card, image, run) -> list[Candidate]` and `main()` with `--bench/--card/--image/--run/--format` CLI flags. Loads `discover_validated_runs` from `harvest_validated_results` via `importlib`. **Heuristic**: for each agent test function, extracts a `TestBehavior` (normalized name, docstring, `frozenset` of engine API names via `ast.walk`). A behavior is covered if any audited function matches by (1) normalized name equality or (2) engine-API Jaccard ≥ 0.8 AND ≥1 shared docstring keyword (length > 3). Uncovered behaviors are emitted as `Candidate` dataclass instances; cards with no audited file produce candidates with `note="no audited baseline"`. **Never promotes anything.** Output formats: human-readable `text` (default) or `json`. |

## Directory Structure

```
scripts/
├── build_card_id_map.py           — Scryfall → card_id_map.json builder
├── generate_audited_stubs.py      — sos.json → sos_stubs.py generator
├── harvest_validated_results.py   — Phase 19 harvest pipeline: discovery + row emission + CLI
└── mine_promotion_candidates.py   — Discovery-candidate miner: AST-scans agent tests vs audited suite
```
