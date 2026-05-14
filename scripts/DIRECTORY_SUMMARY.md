# Directory Summary — `scripts/`

## Purpose

Standalone utility scripts for data pipeline tasks. Not part of the main package — run directly via `python scripts/<script>.py`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `build_card_id_map.py` | 230 | Fetches card data from Scryfall API and builds `data/replays/card_id_map.json`. Creates `grpId_to_card_name` forward map and `card_name_to_grpIds` reverse map (list-valued for duplicate-name disambiguation). Adds synthetic entries for SPG #74–83 (grpIds 94700–94709) flagged with `"synthetic": true`. Includes error handling for curl/Scryfall API failures. |
| `generate_audited_stubs.py` | 381 | Reads `benchmarks/sos/data/sos.json` and generates `cards/stubs/sos_stubs.py` containing one stub class per card with colors, hybrid mana, planeswalker loyalty, Vehicle P/T, and `register_sos_stubs(registry)`. |
| `generate_fdn_specs.py` | 308 | Fetches FDN card data from Scryfall and generates the `cards/fdn/` directory tree — 286 subdirectories (by collector number) each with `card_spec.json` and a template `card_impl.py`. |
| `download_replays.py` | 205 | Downloads replay data files for validation testing. |

## Dependencies

- **External**: `requests` (HTTP), Scryfall API
- **Downstream**: `data/replays/card_id_map.json` consumed by `silverquillm/replay/parser.py` and `silverquillm/replay/executor.py`. `cards/stubs/sos_stubs.py` consumed by `tests/audited/sos/conftest.py`. `cards/fdn/*/card_spec.json` consumed by per-card `card_impl.py` files and `cards/registry.py`.

## Directory Structure

```
scripts/
├── build_card_id_map.py        — Scryfall → card_id_map.json builder
├── download_replays.py         — Replay data downloader
├── generate_audited_stubs.py   — sos.json → sos_stubs.py generator
└── generate_fdn_specs.py       — Scryfall → cards/fdn/ directory tree generator
```
