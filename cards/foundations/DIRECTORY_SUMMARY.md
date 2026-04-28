# Directory Summary — `cards/foundations/`

## Purpose

Card implementations for the **Magic: The Gathering Foundations (FDN)** set. Contains 35 playable cards across four categories: basic lands, vanilla/French vanilla creatures, instants/sorceries, and enchantments/artifacts. All cards are verified against Scryfall data.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `basic_lands.py` | 226 | **5 basic lands**: Plains, Island, Swamp, Mountain, Forest. Each subclasses `Land` with `Supertype.BASIC`, land-type subtypes, and a `ManaAbility` that taps for one colored mana. `register_basic_lands(registry)` helper. |
| `simple_creatures.py` | 279 | **15 creatures** (5 vanilla + 10 French vanilla). Uses `make_vanilla()` factory for dynamic `Creature` subclass creation. Vanilla: Aegis Turtle, Savannah Lions, Bear Cub, Swab Goblin, Highborn Vampire. French vanilla: Healer's Hawk, Bishop's Soldier, Leonin Skyhunter, Thornweald Archer, Raging Redcap, Brazen Scourge, Vampire Nighthawk, Magnigoth Sentry, Serra Angel, Tajuru Pathwarden. `register_simple_creatures(registry)`. |
| `simple_spells.py` | 730 | **10 instants/sorceries**: Burst Lightning, Incinerating Blast (damage), Giant Growth (buff via layer 7c), Quick Study (draw), Hero's Downfall (removal), Negate, Cancel (counter), Disenchant (destroy artifact/enchantment), Pilfer (hand disruption), Cemetery Recruitment (graveyard recursion). `register_simple_spells(registry)`. |
| `simple_permanents.py` | 615 | **5 noncreature permanents**: Pacifism (aura debuff — can't attack/block), Untamed Hunger (aura +2/+1 menace), Unflinching Courage (aura +2/+2 trample lifelink), Hedron Archive (mana rock — tap for {C}{C}), Goblin Oriflamme (attacking creatures +1/+0). `register_simple_permanents(registry)`. |

## Important Classes / Functions

- **`make_vanilla(name, cost_str, power, toughness, keywords, creature_types)`** — Factory that dynamically creates `Creature` subclasses for stat-only creatures.
- **Each card class** (e.g., `BurstLightning`, `Pacifism`, `SerraAngel`) — Subclasses `CardImpl` subtypes, overrides `get_targets()`, `on_resolve()`, `on_cast()` as needed.
- **`register_*` functions** — Register all cards in a category with a `CardRegistry`, including `CardMetadata`.
- **`_get_chosen_target(card, game)`** — Shared helper to retrieve the target chosen during casting (via `card.chosen_targets` or test backdoor `card._resolve_target`).

## Patterns

- **Aura implementation**: Subclass `Aura`, override `get_targets()` for legal targets, `on_resolve()` to attach and register continuous effect. Apply functions guard against aura leaving battlefield.
- **Targeted spells**: Override `can_cast()` to return `False` when no legal targets exist. Targets accessed via `self.chosen_targets` (set by `cast_spell()`).
- **Continuous effects**: Spells/auras register effects via `game.effect_manager.add()` with appropriate `Layer`/`SubLayer` and duration.

## Dependencies

- **`engine/card.py`** — Base classes: `Land`, `Creature`, `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`.
- **`engine/types.py`** — `ManaCost`, `ManaType`, `Keyword`, `CardType`, `Supertype`, `TargetRequirement`, `Zone`.
- **`engine/continuous_effects.py`** — `ContinuousEffect`, `Layer`, `SubLayer`, duration constants.
- **`cards/registry.py`** — `CardRegistry`, `CardMetadata` for registration.

## Testing

- `tests/cards/test_basic_lands.py` — 30+ tests for land tapping, mana production, registry.
- `tests/cards/test_simple_creatures.py` — Stats, keywords, registry, combat integration.
- `tests/cards/test_simple_spells.py` — Attributes, targeting, resolution, registry.
- `tests/cards/test_simple_permanents.py` — Aura attachment, continuous effects, combat restrictions, SBAs, mana abilities.
