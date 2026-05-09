# Directory Summary — `tests/cards/`

## Purpose

Unit tests for all card implementations in `cards/` and `cards/foundations/`. Tests verify card attributes (mana cost, power/toughness, keywords), targeting, resolution effects, registry integration, and game mechanics interactions. **25 test files** covering 250+ card implementations.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `test_registry.py` | CardRegistry API — register, get, create_instance, list_all. |
| `test_scryfall.py` | Scryfall API fetch + parse + caching. |
| `test_basic_lands.py` | 5 basic lands — tapping, mana production, supertypes. |
| `test_simple_creatures.py` | 15 creatures — stats, keywords, combat, make_vanilla factory. |
| `test_vanilla_creatures_batch2.py` | 7 batch 2 creatures — stats, keywords, registry. |
| `test_simple_spells.py` | 10 instants/sorceries — targeting, resolution, counter spells. |
| `test_simple_spells_batch2.py` | 15 batch 2 non-targeted spells — draw, lifegain, tokens. |
| `test_simple_spells_batch2_edges.py` | Edge cases for batch 2 spells. |
| `test_simple_spells_batch3.py` | 18 batch 3 targeted spells — fizzle, controller filtering. |
| `test_simple_permanents.py` | 5 noncreature permanents — aura attachment, continuous effects, combat restrictions. |
| `test_enchantments.py` | 8 enchantments — aura buffs, global enchantment effects. |
| `test_auras_batch2.py` | 10 batch 2 auras — death triggers, counters, sacrifice. |
| `test_global_enchantments.py` | 10 non-aura enchantments — anthems, triggers, exile-until-leaves. |
| `test_planeswalkers.py` | 4 planeswalkers — loyalty abilities, counter management. |
| `test_planeswalkers_batch2.py` | 3 batch 2 planeswalkers — Kaito, Chandra, Vivien. |
| `test_modal_spells.py` | 8 modal spells — mode selection, resolution for each mode. |
| `test_complex_spells.py` | 16 complex cards — modal, X-cost, kicker spells and creatures. |
| `test_artifacts.py` | 10 artifacts — mana rocks, equipment attach/detach, utility. |
| `test_artifacts_batch2.py` | 27 batch 2 artifacts — mana rocks, vehicles, artifact creatures. |
| `test_equipment.py` | 7 equipment — equip abilities, combat triggers, landfall, ETB auto-attach. |
| `test_lands.py` | 13 non-basic lands — gain lands, utility lands. |
| `test_etb_creatures.py` | 29 ETB trigger creatures — draw, tokens, damage, destroy, exile, bounce. |
| `test_death_trigger_creatures.py` | 17 death trigger creatures — tokens, draw, drain, recursion. |
| `test_activated_creatures.py` | 19 activated ability creatures — mana, tap, sacrifice, pump. |
| `test_foundations_batch1_integration.py` | Cross-category integration tests for batch 1 cards. |

## Dependencies

- `tests/test_utils.py` — `create_game`, `set_board_state`, `cast_spell` helpers.
- `cards/foundations/` — Card classes under test.
- `engine/` — Game state, casting, combat, continuous effects.
