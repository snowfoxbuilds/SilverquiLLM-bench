# Directory Summary — `tests/cards/`

## Purpose

Unit tests for card implementations and the card registry/data pipeline. Contains ~270 test functions covering card attributes, targeting, resolution, registry integration, and Scryfall data parsing.

## Key Files

| File | Tests | Covers |
|------|-------|--------|
| `test_registry.py` | 35 | `CardRegistry` register/get/create_instance/list_all, `CardMetadata` construction, duplicate registration, missing card lookup |
| `test_scryfall.py` | 35 | `fetch_set()` pagination, caching, `_parse_card()` field extraction, rate limiting, error handling (uses mocking) |
| `test_basic_lands.py` | 30+ | Basic land attributes (supertypes, subtypes), mana abilities, tap-for-mana resolution, `register_basic_lands`, registry metadata |
| `test_simple_creatures.py` | 34 | Creature stats (power/toughness), keywords, mana costs, `make_vanilla` factory, registry integration, combat behavior |
| `test_simple_spells.py` | 30+ | Spell attributes, targeting (`get_targets`), resolution (`on_resolve`), `can_cast` guards, registry metadata |
| `test_simple_permanents.py` | 34 | Aura attachment, continuous effect registration, combat restrictions (Pacifism), P/T modification (Untamed Hunger, Unflinching Courage), mana abilities (Hedron Archive), non-aura enchantments (Goblin Oriflamme), SBA interaction |

## Dependencies

- **`cards/`** — All modules under test: `registry.py`, `scryfall.py`, `cards/foundations/*.py`.
- **`engine/`** — Engine modules for game state setup: `game_state.py`, `player.py`, `card.py`, `types.py`, `zones.py`.
- **`tests/test_utils.py`** — Some tests use shared test utilities.

## Testing Approach

- **Card correctness**: Tests verify card attributes match Scryfall data (power, toughness, mana cost, keywords, type line).
- **Behavioral tests**: Tests for spells and permanents exercise `get_targets()`, `on_resolve()`, `on_cast()` hooks with mock/real game states.
- **Registry roundtrip**: Tests verify register → lookup → create_instance pipeline produces correct card objects.
- **Scryfall mocking**: `test_scryfall.py` mocks HTTP calls to avoid real API hits in CI.
