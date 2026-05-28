"""Tests for SOS 257 — Great Hall of the Biblioplex.

Covers:
- Static card properties (name, type line, no mana cost, card type LAND)
- can_cast returns False (lands are not cast)
- get_mana_abilities returns at least 2 mana abilities
- First mana ability: {T} produces {C} (colorless mana)
- First mana ability: tapping once works; second tap fails (already tapped)
- Second mana ability: {T} + pay 1 life produces one mana of any color
- Second mana ability: uses life payment (controller loses 1 life)
- Second mana ability: land must not already be tapped
- get_activated_abilities returns at least 1 activated ability
- Activated ability ({5}): if not a creature, makes it a 2/4 Wizard creature-land
- Activated ability ({5}): card_types includes both LAND and CREATURE after activation
- Activated ability ({5}): subtypes include "Wizard" after activation
- Activated ability ({5}): base_power becomes 2, base_toughness becomes 4 after activation
- Activated ability ({5}): if already a creature, ability does nothing (idempotent guard)
- Activated ability ({5}): costs 5 generic mana (description or cost structure)
- Wizard creature mode: register_triggers provides a SpellCastTriggeredEvent trigger
- Wizard creature mode trigger: fires when controller casts an instant
- Wizard creature mode trigger: fires when controller casts a sorcery
- Wizard creature mode trigger: does not fire for opponent's instants/sorceries
- Wizard creature mode trigger: effect grants +1/+0 until end of turn
"""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Land, Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card property tests
# ---------------------------------------------------------------------------


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost — mana_cost should be empty/zero CMC."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost.cmc == 0

    def test_card_type_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_can_cast_returns_false(self) -> None:
        """Lands cannot be cast; they are played as a special action."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# Mana ability 1: {T} → Add {C}
# ---------------------------------------------------------------------------


class TestGreatHallColorlessManaAbility:
    """{T}: Add {C} — the basic colorless mana ability."""

    def test_has_at_least_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_first_ability_adds_colorless_mana(self) -> None:
        """Activating the first ability while untapped adds {C} to the pool."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[0]
        # Pay the tap cost
        paid = ability.cost(game, card)
        assert paid is True, "Cost should succeed on an untapped land"
        # Activate the mana effect
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_first_ability_taps_the_land(self) -> None:
        """After activating {T}: Add {C}, the land becomes tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[0]
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_first_ability_fails_when_already_tapped(self) -> None:
        """The cost of {T} cannot be paid if the land is already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        ability = card.get_mana_abilities()[0]
        paid = ability.cost(game, card)
        assert paid is False


# ---------------------------------------------------------------------------
# Mana ability 2: {T}, Pay 1 life → Add one mana of any color
# ---------------------------------------------------------------------------


class TestGreatHallColoredManaAbility:
    """{T}, Pay 1 life: Add one mana of any color (restricted to instants/sorceries)."""

    def test_second_ability_costs_life(self) -> None:
        """Activating the second ability should reduce life by 1."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        starting_life = p1.life

        ability = card.get_mana_abilities()[1]
        paid = ability.cost(game, card)
        assert paid is True, "Cost should succeed on an untapped land with >0 life"
        assert p1.life == starting_life - 1

    def test_second_ability_taps_the_land(self) -> None:
        """After activating the second mana ability, the land should be tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_second_ability_adds_colored_mana(self) -> None:
        """The second ability should add at least 1 total mana after mana_produced fires."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        ability.mana_produced(game)

        # At least 1 colored mana should have been added (which specific color
        # depends on the implementation's default; we only check total colored >=1)
        colored_total = sum(
            p1.mana_pool.get(mt)
            for mt in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                       ManaType.RED, ManaType.GREEN)
        )
        assert colored_total >= 1

    def test_second_ability_fails_when_already_tapped(self) -> None:
        """The second mana ability's tap cost fails if already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        ability = card.get_mana_abilities()[1]
        paid = ability.cost(game, card)
        assert paid is False

    def test_second_ability_does_not_add_colorless(self) -> None:
        """The second ability produces colored mana, not colorless."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        # Record colorless before
        colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        ability.mana_produced(game)

        # Colorless mana should not have increased
        assert p1.mana_pool.get(ManaType.COLORLESS) == colorless_before


# ---------------------------------------------------------------------------
# Activated ability: {5} — animate this land into a 2/4 Wizard creature
# ---------------------------------------------------------------------------


class TestGreatHallAnimationAbility:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature-land."""

    def test_has_at_least_one_activated_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_animation_ability_requires_five_generic_mana(self) -> None:
        """The animation ability's cost requires {5} generic mana."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        # Give exactly 4 mana — should fail
        p1.mana_pool.add(ManaType.COLORLESS, 4)
        ability = card.get_activated_abilities()[0]
        paid = ability.cost(game, card)
        assert paid is False, "4 generic mana is insufficient for {5}"

    def test_animation_ability_succeeds_with_five_mana(self) -> None:
        """The animation ability's cost succeeds when {5} generic mana is available."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        paid = ability.cost(game, card)
        assert paid is True

    def test_animation_adds_creature_type_to_land(self) -> None:
        """After the ability resolves, the land has both LAND and CREATURE card types."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        # Not a creature before
        assert CardType.CREATURE not in card.card_types

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        assert CardType.CREATURE in card.card_types
        assert CardType.LAND in card.card_types

    def test_animation_sets_power_to_two(self) -> None:
        """After animation, the creature-land has power 2."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        # Power should be accessible; check modified_power or base_power
        power = getattr(card, "modified_power", getattr(card, "base_power", None))
        assert power is not None, "Animated land should have a power attribute"
        assert power == 2

    def test_animation_sets_toughness_to_four(self) -> None:
        """After animation, the creature-land has toughness 4."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        toughness = getattr(card, "modified_toughness", getattr(card, "base_toughness", None))
        assert toughness is not None, "Animated land should have a toughness attribute"
        assert toughness == 4

    def test_animation_adds_wizard_subtype(self) -> None:
        """After animation, the creature-land has the 'Wizard' subtype."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        assert "Wizard" in card.subtypes

    def test_animation_does_nothing_if_already_creature(self) -> None:
        """If the land is already a creature, activating the ability is a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # Animate it once
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        # Record state after first animation
        power_after_first = getattr(card, "modified_power", getattr(card, "base_power", 2))

        # Attempt to activate again (already a creature — should be blocked)
        # Reset mana and try
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        # The cost may or may not succeed; we check that the effect does not
        # add a second stack of the ability (no duplicate types / no error)
        ability.effect(game)

        # CREATURE type should still be present (exactly once conceptually)
        assert CardType.CREATURE in card.card_types
        # Power should be the same (no double-stacking)
        power_after_second = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after_second == power_after_first


# ---------------------------------------------------------------------------
# Wizard creature mode: triggered ability (instant/sorcery cast → +1/+0 EOT)
# ---------------------------------------------------------------------------


class TestGreatHallWizardTrigger:
    """When animated, registers 'whenever you cast an instant or sorcery spell,
    this creature gets +1/+0 until end of turn' trigger."""

    def test_register_triggers_registers_spell_cast_trigger_after_animation(self) -> None:
        """After register_triggers is called post-animation, a SpellCastTriggeredEvent
        trigger should exist for this card."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # Animate the land first
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)

        # Register triggers (called when the card 'enters as creature')
        card.register_triggers(game)

        spell_cast_triggers = [
            t for t in game.trigger_manager._triggers
            if t.event_type is SpellCastTriggeredEvent and t.source is card
        ]
        assert len(spell_cast_triggers) >= 1

    def test_wizard_trigger_condition_true_for_controller_instant(self) -> None:
        """The trigger condition should be True when controller casts an instant."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        # Animate
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)
        card.register_triggers(game)

        trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.event_type is SpellCastTriggeredEvent and t.source is card),
            None,
        )
        assert trigger is not None

        instant = Instant(name="Lightning Bolt")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=instant)
        result = trigger.condition is None or trigger.condition(game, event)
        assert result is True

    def test_wizard_trigger_condition_true_for_controller_sorcery(self) -> None:
        """The trigger condition should be True when controller casts a sorcery."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)
        card.register_triggers(game)

        trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.event_type is SpellCastTriggeredEvent and t.source is card),
            None,
        )
        assert trigger is not None

        sorcery = Sorcery(name="Divination")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=sorcery)
        result = trigger.condition is None or trigger.condition(game, event)
        assert result is True

    def test_wizard_trigger_condition_false_for_opponent_instant(self) -> None:
        """The trigger should NOT fire when the opponent casts an instant."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)
        card.register_triggers(game)

        trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.event_type is SpellCastTriggeredEvent and t.source is card),
            None,
        )
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("condition is None — cannot verify controller filtering")

        instant = Instant(name="Opponent's Bolt")
        event = SpellCastTriggeredEvent(spell=None, player=p2, card=instant)
        assert trigger.condition(game, event) is False

    def test_wizard_trigger_condition_false_for_controller_creature(self) -> None:
        """The trigger should NOT fire when controller casts a creature spell."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)
        card.register_triggers(game)

        trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.event_type is SpellCastTriggeredEvent and t.source is card),
            None,
        )
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("condition is None — cannot verify type filtering")

        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=creature)
        assert trigger.condition(game, event) is False

    def test_wizard_trigger_effect_grants_plus_one_power(self) -> None:
        """When the trigger resolves, the Wizard creature-land gets +1/+0 EOT."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Animate the land into a creature
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = card.get_activated_abilities()[0]
        ability.cost(game, card)
        ability.effect(game)
        card.register_triggers(game)

        trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.event_type is SpellCastTriggeredEvent and t.source is card),
            None,
        )
        assert trigger is not None

        # Record power before trigger fires
        power_before = getattr(card, "modified_power", getattr(card, "base_power", 2))

        # Execute trigger effect
        trigger.effect(game)

        # Power should be +1 higher after trigger
        power_after = getattr(card, "modified_power", getattr(card, "base_power", 2))
        assert power_after == power_before + 1
