# Directory Summary — `cards/foundations/`

## Purpose

Card implementations for the **Magic: The Gathering Foundations (FDN)** set. Contains **260+ playable cards** across 21 implementation files covering all major card categories: basic lands, vanilla/French vanilla creatures, instants/sorceries (simple, targeted, modal, complex), enchantments (auras + global), artifacts, equipment, planeswalkers, ETB/death/activated-ability creatures, non-basic lands, X-cost/kicker/modal cards, and Special Guest (SPG) cards. All cards verified against Scryfall data.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `basic_lands.py` | **5 basic lands**: Plains, Island, Swamp, Mountain, Forest. Each subclasses `Land` with `Supertype.BASIC` and a `ManaAbility`. `register_basic_lands(registry)`. |
| `simple_creatures.py` | **15 creatures** (5 vanilla + 10 French vanilla). Uses `make_vanilla()` factory. `register_simple_creatures(registry)`. |
| `vanilla_creatures_batch2.py` | **7 FDN creatures**: Fire Elemental, Gigantosaurus, Quakestrider Ceratops, Elementalist Adept, Skyraker Giant, Swiftblade Vindicator, Zetalpa Primal Dawn. |
| `simple_spells.py` | **10 instants/sorceries**: Burst Lightning, Giant Growth, Hero's Downfall, Negate, Cancel, etc. `register_simple_spells(registry)`. |
| `simple_spells_batch2.py` | **15 non-targeted FDN spells**: draw, lifegain, tokens, each-player effects (Embrace the Paradox, Rapturous Moment, Wisdom of Ages, etc.). |
| `simple_spells_batch3.py` | **18 targeted FDN spells**: fizzle-safe `on_resolve`, controller-filtered `get_targets`, power-based damage reads. |
| `simple_permanents.py` | **5 noncreature permanents**: Pacifism, Untamed Hunger, Unflinching Courage (auras), Hedron Archive, Goblin Oriflamme. `register_simple_permanents(registry)`. |
| `enchantments.py` | **8 enchantments**: 4 auras (Holy Strength, Unholy Strength, etc.) + 4 global enchantments with continuous effects. `register_enchantments(registry)`. |
| `auras_batch2.py` | **10 FDN auras**: with death triggers, counters, move_to_zone for sacrifice, ENGINE LIMITATION comments. |
| `global_enchantments.py` | **10 non-aura enchantments**: anthems (Anthem of Champions, Goblin Oriflamme), keyword-granting (Garruk's Uprising), static (Authority of the Consuls), triggers (Phyrexian Arena, Impact Tremors, Rite of the Dragoncaller, Painful Quandary), exile-until-leaves (Banishing Light), activated (Vampiric Rites). |
| `planeswalkers.py` | **4 planeswalkers**: Ajani, Caller of the Pride and 3 others with loyalty abilities. `register_planeswalkers(registry)`. |
| `planeswalkers_batch2.py` | **3 FDN planeswalkers**: Kaito Cunning Infiltrator, Chandra Flameshaper, Vivien Reid with fully implemented loyalty abilities. |
| `modal_spells.py` | **8 modal spells**: "Choose one" / "choose one or both" spells like Abzan Charm with `Mode` definitions and `on_resolve()`. `register_modal_spells(registry)`. |
| `complex_spells.py` | **16 complex FDN cards**: modal instants/sorceries (Abrade, Valorous Stance, etc.), X-cost spells (Exsanguinate, Primal Might, Finale of Revelation), kicker spells (Burst Lightning, Into the Roil), kicker creatures (Gnarlid Colony, Gatekeeper of Malakir). |
| `artifacts.py` | **10 artifacts**: Mana rocks (Sol Ring, Arcane Signet), equipment, and utility artifacts. `register_artifacts(registry)`. |
| `artifacts_batch2.py` | **27 remaining FDN artifacts**: mana rocks, utility artifacts, equipment, vehicles, artifact creatures (Darksteel Colossus, Steel Hellkite, Ramos Dragon Engine, etc.). |
| `equipment.py` | **7 FDN equipment**: with `get_activated_abilities()` equip abilities, combat damage trigger (Goldvein Pick), landfall trigger (Adventuring Gear), ETB auto-attach (Celestial Armor). |
| `lands.py` | **13 FDN non-basic lands**: 10 gain lands (ETB tapped, gain 1 life, dual-color mana), 3 utility lands (Rogue's Passage, Soulstone Sanctuary, Evolving Wilds). |
| `etb_creatures.py` | **29 FDN ETB creatures**: draw, lifegain, tokens, damage, destroy, exile, bounce, graveyard recursion, counters, discard, debuff triggers. |
| `death_trigger_creatures.py` | **17 FDN creatures with death triggers**: token creation, draw, mill/surveil, drain/damage, graveyard recursion, library effects. |
| `activated_creatures.py` | **19 FDN creatures with activated abilities**: mana (Llanowar Elves, Elvish Archdruid), tap abilities (Krenko Mob Boss), sacrifice abilities (Cathar Commando), pump abilities (Shivan Dragon), other (Spectral Sailor, Scavenging Ooze, Reassembling Skeleton). |

| `special_guests.py` | **10 Special Guest (SPG) cards**: Condemn, Grim Tutor, Paradise Druid, Goblin Bushwhacker (kicker), Sphinx's Tutelage (mill trigger), Embercleave (flash, ETB attach, P/T bonus), Akroma's Memorial (keyword anthem), Temporal Manipulation (extra turn), Fiend Artisan (sacrifice-search). `register_special_guests(registry)`. |

## Important Classes / Functions

- **`make_vanilla(name, cost_str, power, toughness, keywords, creature_types)`** — Factory for stat-only `Creature` subclasses.
- **Each card class** — Subclasses appropriate engine base class; overrides `get_targets()`, `on_resolve()`, `on_cast()`, `get_mana_abilities()`, `get_loyalty_abilities()`, `get_activated_abilities()`, `get_triggers()` as needed.
- **`register_*` functions** — Register all cards in a category with a `CardRegistry` including `CardMetadata`.
- **`_get_chosen_target(card, game)`** — Shared helper for targeted spells.

## Patterns

- **Aura implementation**: Subclass `Aura`, override `get_targets()` and `on_resolve()` to attach and register continuous effect.
- **Targeted spells**: Override `can_cast()` for target validation. Targets via `self.chosen_targets`. Fizzle-safe `on_resolve()` checks target validity. `filter_fn` lambdas use lazy predicates (evaluate properties at cast time, not definition time).
- **Continuous effects**: Register via `game.effect_manager.add()` with appropriate `Layer`/`SubLayer` and duration.
- **Modal spells**: Define `Mode` objects on the class; `on_resolve()` checks `self.chosen_modes`.
- **Planeswalkers**: Define `LoyaltyAbility` objects; loyalty counter management via engine.
- **ETB triggers**: Return `TriggerRegistration` from `get_triggers()` with `EventType.ENTERS_BATTLEFIELD` condition.
- **Death triggers**: Return `TriggerRegistration` from `get_triggers()` with `EventType.CREATURE_DIES` condition.
- **Equipment**: Use `get_activated_abilities()` for equip costs; continuous effects on equipped creature.
- **Kicker**: Check `self.kicker_paid` in `on_resolve()` for enhanced effects.
- **X-cost**: Read `self.x_value` in `on_resolve()` for variable effects.

## Dependencies

- **`engine/card.py`** — Base classes: `Land`, `Creature`, `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`, `ArtifactCreature`, `Planeswalker`.
- **`engine/types.py`** — `ManaCost`, `ManaType`, `Keyword`, `CardType`, `Supertype`, `TargetRequirement`, `Zone`.
- **`engine/continuous_effects.py`** — `ContinuousEffect`, `Layer`, `SubLayer`.
- **`engine/triggers.py`** — `EventType`, `TriggerRegistration`.
- **`engine/zones.py`** — `move_to_zone()` for zone transitions.
- **`engine/game.py`** — Helper actions (`deal_damage`, `destroy`, `create_token`, `add_counter`, etc.).
- **`cards/registry.py`** — `CardRegistry`, `CardMetadata`.

## Testing

- `tests/cards/test_basic_lands.py` — Land tapping, mana production, registry.
- `tests/cards/test_simple_creatures.py` — Stats, keywords, combat integration.
- `tests/cards/test_vanilla_creatures_batch2.py` — Batch 2 creature stats, keywords, registry.
- `tests/cards/test_simple_spells.py` — Targeting, resolution, registry.
- `tests/cards/test_simple_spells_batch2.py` — Batch 2 non-targeted spells.
- `tests/cards/test_simple_spells_batch2_edges.py` — Edge cases for batch 2 spells.
- `tests/cards/test_simple_spells_batch3.py` — Batch 3 targeted spells.
- `tests/cards/test_simple_permanents.py` — Aura attachment, continuous effects, combat restrictions.
- `tests/cards/test_enchantments.py` — Enchantment cards (auras and global).
- `tests/cards/test_auras_batch2.py` — Batch 2 auras.
- `tests/cards/test_global_enchantments.py` — Non-aura enchantments.
- `tests/cards/test_planeswalkers.py` — Planeswalker loyalty abilities.
- `tests/cards/test_planeswalkers_batch2.py` — Batch 2 planeswalkers.
- `tests/cards/test_modal_spells.py` — Modal spell resolution.
- `tests/cards/test_complex_spells.py` — Complex/modal/X-cost/kicker spells.
- `tests/cards/test_artifacts.py` — Artifact cards (mana rocks, equipment, utility).
- `tests/cards/test_artifacts_batch2.py` — Batch 2 artifacts.
- `tests/cards/test_equipment.py` — Equipment cards.
- `tests/cards/test_lands.py` — Non-basic lands.
- `tests/cards/test_etb_creatures.py` — ETB trigger creatures.
- `tests/cards/test_death_trigger_creatures.py` — Death trigger creatures.
- `tests/cards/test_activated_creatures.py` — Activated ability creatures.
- `tests/cards/test_special_guests.py` — 10 Special Guest cards and registration.
- `tests/cards/test_foundations_batch1_integration.py` — Cross-category integration tests.
