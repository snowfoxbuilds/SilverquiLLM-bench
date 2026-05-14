# Directory Summary — `cards/fdn/`

## Purpose

Per-card implementations and legacy monolithic modules for the MTG Foundations (FDN) set. Contains 286 subdirectories (one per collector number) each with a `card_spec.json` (Scryfall-sourced metadata) and `card_impl.py` (implementation subclassing `CardImpl`). The `_legacy/` subdirectory preserves the original monolithic implementation files (22 modules) for backward compatibility.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Empty package init for importability. |
| `utils.py` | Shared helpers used across per-card implementations: `TapLand` (land base class with tap-for-mana), `GainLand` (ETB gain-1-life tap land), `make_vanilla()` (factory for vanilla creatures), `_tap_cost()` (tap cost helper). |

## Subdirectories

| Directory | Contents |
|-----------|----------|
| `1/` – `291/`, `spg_74/` – `spg_83/` | **Per-card directories** (286 total). Each contains `card_spec.json` (Scryfall card data) and `card_impl.py` (implementation class with default `name` from spec). |
| `_legacy/` | **Legacy monolithic modules** — 22 Python files migrated from the deleted `cards/foundations/` directory. Contains the original grouped implementation files (`simple_creatures.py`, `artifacts.py`, `planeswalkers.py`, etc.) plus `__init__.py`. Used by existing tests that import from `cards.fdn._legacy`. |

## Architecture

- **Per-card pattern**: Each card has its own directory (`{collector_number}/`) with a `card_impl.py` that defines a single `CardImpl` subclass. The class's default `name` is read from `card_spec.json` in the same directory.
- **Registry integration**: `cards/registry.py` → `register_fdn_cards()` walks all per-card directories, imports each `card_impl.py`, and registers the implementation class.
- **Shared utilities**: Common patterns (tap lands, gain lands, vanilla creatures) are factored into `utils.py` to avoid duplication across 286 card files.
- **Legacy bridge**: `_legacy/` provides import compatibility for test files that reference the old `cards.foundations.*` module paths (now `cards.fdn._legacy.*`).

## Dependencies

- **`engine/`** — `CardImpl` and subclasses (`Creature`, `Land`, `Instant`, etc.), `ManaCost`, `ManaType`, `Keyword`, etc.
- **`cards/registry.py`** — `register_fdn_cards()` imports from per-card directories.
- **Upstream**: `scripts/generate_fdn_specs.py` generates the per-card directory structure and `card_spec.json` files.

## Testing

- `tests/test_fdn_card_migration.py` — Validates per-card file counts, `CardImpl` subclasses, registry population, and spot-checks.
- `tests/audited/fdn/` — 1487 per-card audited tests (conftest injects implementations via `CardRegistry`).
- `tests/cards/` — 25 per-category test files (import from `cards.fdn._legacy`).
