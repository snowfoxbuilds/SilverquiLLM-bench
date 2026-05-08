# Directory Summary — `cards/foundations/`

## Purpose

Card implementations for the **Magic: The Gathering Foundations (FDN)** set. Contains 65+ playable cards across seven categories: basic lands, vanilla/French vanilla creatures, instants/sorceries, enchantments/artifacts (simple permanents), enchantments (auras + global), planeswalkers, modal spells, and artifacts. All cards verified against Scryfall data.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `basic_lands.py` | **5 basic lands**: Plains, Island, Swamp, Mountain, Forest. Each subclasses `Land` with `Supertype.BASIC` and a `ManaAbility`. `register_basic_lands(registry)`. |
| `simple_creatures.py` | **15 creatures** (5 vanilla + 10 French vanilla). Uses `make_vanilla()` factory. `register_simple_creatures(registry)`. |
| `simple_spells.py` | **10 instants/sorceries**: Burst Lightning, Giant Growth, Hero's Downfall, Negate, Cancel, etc. `register_simple_spells(registry)`. |
| `simple_permanents.py` | **5 noncreature permanents**: Pacifism, Untamed Hunger, Unflinching Courage (auras), Hedron Archive, Goblin Oriflamme. `register_simple_permanents(registry)`. |
| `enchantments.py` | **8 enchantments**: 4 auras (Holy Strength, Unholy Strength, etc.) + 4 global enchantments with continuous effects. `register_enchantments(registry)`. |
| `planeswalkers.py` | **4 planeswalkers**: Ajani, Caller of the Pride and 3 others with loyalty abilities. `register_planeswalkers(registry)`. |
| `modal_spells.py` | **8 modal spells**: "Choose one" / "choose one or both" spells like Abzan Charm with `Mode` definitions and `on_resolve()`. `register_modal_spells(registry)`. |
| `artifacts.py` | **10 artifacts**: Mana rocks (Sol Ring, Arcane Signet), equipment, and utility artifacts. `register_artifacts(registry)`. |

## Important Classes / Functions

- **`make_vanilla(name, cost_str, power, toughness, keywords, creature_types)`** — Factory for stat-only `Creature` subclasses.
- **Each card class** — Subclasses appropriate engine base class; overrides `get_targets()`, `on_resolve()`, `on_cast()`, `get_mana_abilities()`, `get_loyalty_abilities()` as needed.
- **`register_*` functions** — Register all cards in a category with a `CardRegistry` including `CardMetadata`.
- **`_get_chosen_target(card, game)`** — Shared helper for targeted spells.

## Patterns

- **Aura implementation**: Subclass `Aura`, override `get_targets()` and `on_resolve()` to attach and register continuous effect.
- **Targeted spells**: Override `can_cast()` for target validation. Targets via `self.chosen_targets`.
- **Continuous effects**: Register via `game.effect_manager.add()` with appropriate `Layer`/`SubLayer` and duration.
- **Modal spells**: Define `Mode` objects on the class; `on_resolve()` checks `self.chosen_modes`.
- **Planeswalkers**: Define `LoyaltyAbility` objects; loyalty counter management via engine.

## Dependencies

- **`engine/card.py`** — Base classes: `Land`, `Creature`, `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`, `ArtifactCreature`, `Planeswalker`.
- **`engine/types.py`** — `ManaCost`, `ManaType`, `Keyword`, `CardType`, `Supertype`, `TargetRequirement`, `Zone`.
- **`engine/continuous_effects.py`** — `ContinuousEffect`, `Layer`, `SubLayer`.
- **`cards/registry.py`** — `CardRegistry`, `CardMetadata`.

## Testing

- `tests/cards/test_basic_lands.py` — Land tapping, mana production, registry.
- `tests/cards/test_simple_creatures.py` — Stats, keywords, combat integration.
- `tests/cards/test_simple_spells.py` — Targeting, resolution, registry.
- `tests/cards/test_simple_permanents.py` — Aura attachment, continuous effects, combat restrictions.
- `tests/cards/test_enchantments.py` — Enchantment cards (auras and global).
- `tests/cards/test_planeswalkers.py` — Planeswalker loyalty abilities.
- `tests/cards/test_modal_spells.py` — Modal spell resolution.
- `tests/cards/test_artifacts.py` — Artifact cards (mana rocks, equipment, utility).
- `tests/cards/test_foundations_batch1_integration.py` — Cross-category integration tests.
