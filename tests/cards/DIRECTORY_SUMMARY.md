# Directory Summary — `tests/cards/`

## Purpose

Unit tests for all card implementations in `cards/` and `cards/foundations/`. Tests verify card attributes (mana cost, power/toughness, keywords), targeting, resolution effects, registry integration, and game mechanics interactions.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `test_registry.py` | CardRegistry API — register, get, create_instance, list_all. |
| `test_scryfall.py` | Scryfall API fetch + parse + caching. |
| `test_basic_lands.py` | 5 basic lands — tapping, mana production, supertypes. |
| `test_simple_creatures.py` | 15 creatures — stats, keywords, combat, make_vanilla factory. |
| `test_simple_spells.py` | 10 instants/sorceries — targeting, resolution, counter spells. |
| `test_simple_permanents.py` | 5 noncreature permanents — aura attachment, continuous effects, combat restrictions. |
| `test_enchantments.py` | 8 enchantments — aura buffs, global enchantment effects. |
| `test_planeswalkers.py` | 4 planeswalkers — loyalty abilities, counter management. |
| `test_modal_spells.py` | 8 modal spells — mode selection, resolution for each mode. |
| `test_artifacts.py` | 10 artifacts — mana rocks, equipment attach/detach, utility. |
| `test_foundations_batch1_integration.py` | Cross-category integration tests for batch 1 cards. |

## Dependencies

- `tests/test_utils.py` — `create_game`, `set_board_state`, `cast_spell` helpers.
- `cards/foundations/` — Card classes under test.
- `engine/` — Game state, casting, combat, continuous effects.
