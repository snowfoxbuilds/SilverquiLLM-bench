# Directory Summary — `cards/`

## Purpose

Card registry, data pipeline, and card implementations for the SilverquiLLM MTG engine. Maps card names to implementation classes and metadata, fetches card data from Scryfall, and houses the `foundations/` subdirectory with actual FDN set card implementations.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `registry.py` | 130 | `CardMetadata` dataclass (11 fields: name, mana_cost_str, type_line, oracle_text, power, toughness, colors, keywords, rarity, set_code, collector_number). `CardRegistry` class (register/get/create_instance/list_all). `default_registry` module-level singleton. |
| `scryfall.py` | 155 | `fetch_set()` — paginated Scryfall API fetcher with 100ms rate limiting and file-based JSON cache under `data/sets/`. `_parse_card()` converts Scryfall JSON to `CardMetadata`. |
| `__init__.py` | — | Package init. |
| `py.typed` | — | PEP 561 typed package marker. |

## Important Classes / Functions

- **`CardRegistry`** — Central registry mapping card name → `(impl_class, CardMetadata)`. `create_instance(name, owner, controller)` instantiates cards.
- **`CardMetadata`** — Scryfall-sourced card data used for validation and display.
- **`fetch_set(set_code)`** — Downloads all cards for a set from Scryfall with caching.
- **`default_registry`** — Module-level singleton for convenience.

## Dependencies

- **`engine/card.py`** — `CardImpl` base class referenced by registry.
- **`engine/player.py`** — `Player` type used in `create_instance`.
- **External**: `urllib` (stdlib) for Scryfall HTTP requests; `json` for cache serialization.

## Subdirectories

- **`foundations/`** — Card implementations for the MTG Foundations (FDN) set. See `foundations/DIRECTORY_SUMMARY.md`.

## Testing

- Tests in `tests/cards/` — `test_registry.py` (registry API), `test_scryfall.py` (API + parsing), plus per-category card tests.
