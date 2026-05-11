# Directory Summary — `data/`

## Purpose

Runtime data directory for cached API responses and replay validation data.

## Key Subdirectories

| Directory | Responsibility |
|-----------|---------------|
| `sets/` | Scryfall JSON cache — cached card data fetched by `cards/scryfall.py`. Includes `sos.json` (full set), `soa_cn1-65.json` (65 SOA Mystical Archives cards), and `spg_cn149-158.json` (10 SPG Special Guest cards). |
| `replays/` | Replay validation data — card ID mappings and sample replay files. |

## Key Files

| File | Responsibility |
|------|---------------|
| `replays/card_id_map.json` | grpId-to-card-name mapping (592 entries: 582 from Scryfall + 10 synthetic SPG). Includes `grpId_to_card_name` and `card_name_to_grpIds` (list-valued for duplicate-name disambiguation). Synthetic entries flagged with `"synthetic": true`. |
| `replays/sample_replay.json` | Synthetic 5-turn replay data with real grpIds for testing the replay parser and executor. |

## Dependencies

- **Upstream**: `scripts/build_card_id_map.py` generates `card_id_map.json`. `cards/scryfall.py` populates `sets/`.
- **Downstream**: `silverquillm/replay/parser.py` and `silverquillm/replay/executor.py` load `card_id_map.json`.

## Directory Structure

```
data/
├── sets/                        — Scryfall JSON cache
│   ├── soa_cn1-65.json          — SOA Mystical Archives subset (65 cards)
│   └── spg_cn149-158.json       — SPG Special Guest subset (10 cards)
└── replays/
    ├── card_id_map.json         — grpId ↔ card name mapping
    └── sample_replay.json       — Synthetic test replay data
```
