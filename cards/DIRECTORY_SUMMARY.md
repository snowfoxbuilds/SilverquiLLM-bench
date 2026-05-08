# Directory Summary — `cards/`

## Purpose

Card registry, data pipeline, and card implementations for the SilverquiLLM MTG engine. Maps card names to implementation classes and metadata, fetches card data from Scryfall, and houses the `foundations/` subdirectory with FDN set card implementations (65+ cards).

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `py.typed` | PEP 561 typed package marker. |
| `registry.py` | `CardMetadata` dataclass (11 fields). `CardRegistry` class (register/get/create_instance/list_all). `default_registry` module-level singleton. |
| `scryfall.py` | `fetch_set()` — paginated Scryfall API fetcher with 100ms rate limiting and file-based JSON cache under `data/sets/`. `_parse_card()` converts Scryfall JSON to `CardMetadata`. |

## Important Classes / Functions

- **`CardRegistry`** — Central registry mapping card name → `(impl_class, CardMetadata)`. `create_instance(name, owner, controller)` instantiates cards.
- **`CardMetadata`** — Scryfall-sourced card data used for validation and display.
- **`fetch_set(set_code)`** — Downloads all cards for a set from Scryfall with caching.
- **`default_registry`** — Module-level singleton.

## Subdirectories

- **`foundations/`** — Card implementations for the MTG Foundations (FDN) set (65+ cards across 7 categories). See `foundations/DIRECTORY_SUMMARY.md`.

## Dependencies

- **`engine/card.py`** — `CardImpl` base class referenced by registry.
- **`engine/player.py`** — `Player` type used in `create_instance`.
- **External**: `urllib` (stdlib) for Scryfall HTTP requests.

## Testing

- Tests in `tests/cards/` — `test_registry.py`, `test_scryfall.py`, plus per-category card tests (8 test files total).
