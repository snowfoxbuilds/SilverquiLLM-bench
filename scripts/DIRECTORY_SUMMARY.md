# Directory Summary — `scripts/`

## Purpose

Standalone utility scripts for data pipeline tasks. Not part of the main package — run directly via `python scripts/<script>.py`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `build_card_id_map.py` | 230 | Fetches card data from Scryfall API and builds `data/replays/card_id_map.json`. Creates `grpId_to_card_name` forward map and `card_name_to_grpIds` reverse map (list-valued for duplicate-name disambiguation). Adds synthetic entries for SPG #74–83 (grpIds 94700–94709) flagged with `"synthetic": true`. Includes error handling for curl/Scryfall API failures. |
| `generate_audited_stubs.py` | ~200 | Reads `benchmarks/sos/data/sos.json` and generates `cards/stubs/sos_stubs.py` containing one stub class per card with colors, hybrid mana, planeswalker loyalty, Vehicle P/T, and `register_sos_stubs(registry)`. |
| `harvest_validated_results.py` | ~380 | **Phase 19 harvest pipeline — discovery + row emission.** Discovers validated results by globbing `docker/*/validated_results/*/`. Exposes `discover_validated_runs(repo_root, *, image, run, card) -> list[ValidatedRun]` (sorted, filtered), `build_rows_for_run(vr, *, harvested_at) -> list[dict]` (one dict per `(card, test_node)` with keys `image, run, card, test_node, outcome, tests_hash, passed, failed, total, complexity_tier, harvested_at`), and `harvest(repo_root, *, bench, output, image, run, card, harvested_at) -> int` (full pipeline: discover → build rows → truncate-write JSONL → return row count). `main()` delegates to `harvest()` and prints a summary. Creates `benchmarks/<bench>/analysis/` on first run. Cards lacking `test_nodes` in `result.json` are skipped (legacy fallback deferred to item 5). |

## Dependencies

- **External**: `requests` (HTTP), Scryfall API
- **Downstream**: `data/replays/card_id_map.json` consumed by `silverquillm/replay/parser.py` and `silverquillm/replay/executor.py`. `cards/stubs/sos_stubs.py` consumed by `tests/audited/sos/conftest.py`. `harvest_validated_results.py` writes to `benchmarks/<bench>/analysis/harvested_results.jsonl`.

## Directory Structure

```
scripts/
├── build_card_id_map.py           — Scryfall → card_id_map.json builder
├── generate_audited_stubs.py      — sos.json → sos_stubs.py generator
└── harvest_validated_results.py   — Phase 19 harvest pipeline: discovery + row emission + CLI
```
