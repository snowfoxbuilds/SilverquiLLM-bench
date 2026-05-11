# Directory Summary — `scripts/`

## Purpose

Standalone utility scripts for data pipeline tasks. Not part of the main package — run directly via `python scripts/<script>.py`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `build_card_id_map.py` | 230 | Fetches card data from Scryfall API and builds `data/replays/card_id_map.json`. Creates `grpId_to_card_name` forward map and `card_name_to_grpIds` reverse map (list-valued for duplicate-name disambiguation). Adds synthetic entries for SPG #74–83 (grpIds 94700–94709) flagged with `"synthetic": true`. Includes error handling for curl/Scryfall API failures. |

## Dependencies

- **External**: `requests` (HTTP), Scryfall API
- **Downstream**: `data/replays/card_id_map.json` consumed by `silverquillm/replay/parser.py` and `silverquillm/replay/executor.py`

## Directory Structure

```
scripts/
└── build_card_id_map.py   — Scryfall → card_id_map.json builder
```
