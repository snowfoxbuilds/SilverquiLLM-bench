"""Tests for SOS 257 — Great Hall of the Biblioplex.

Great Hall of the Biblioplex is a Land with three abilities:
1. {T}: Add {C}.
2. {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
   cast an instant or sorcery spell.
3. {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
   with "Whenever you cast an instant or sorcery spell, this creature
   gets +1/+0 until end of turn." It's still a land.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_card_type_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost == ManaCost()

    def test_cannot_be_cast(self) -> None:
        """Lands cannot be cast (they are played as a special action)."""
        game = create_game()
        card = GreatHallOfTheBiblioplex(owner=game.players[0])
        assert card.can_cast(game) is False


# ---------------------------------------------------------------------------
# Mana ability 1: {T}: Add {C}
# ---------------------------------------------------------------------------


class TestColorlessManaAbility:
    """The first mana ability taps for one colorless mana."""

    def test_has_colorless_mana_ability(self) -> None:
        """get_mana_abilities should include a {T}: Add {C} ability."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1
        assert any(isinstance(a, ManaAbility) for a in abilities)

    def test_colorless_ability_taps_land(self) -> None:
        """Activating the colorless mana ability should tap the land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)

        abilities = card.get_mana_abilities()
        # Find the colorless ability (first one)
        colorless_ability = abilities[0]
        # Pay cost: should tap the land
        result = colorless_ability.cost(game, card)
        assert result is True
        assert card.is_tapped is True

    def test_colorless_ability_adds_colorless_mana(self) -> None:
        """The colorless mana ability should add {C} to the controller's pool."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)

        abilities = card.get_mana_abilities()
        colorless_ability = abilities[0]
        # Pay cost
        colorless_ability.cost(game, card)
        # Produce mana
        colorless_ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) >= 1

    def test_colorless_ability_fails_when_tapped(self) -> None:
        """Cannot activate if the land is already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        game.get_battlefield(p1).add(card)

        abilities = card.get_mana_abilities()
        colorless_ability = abilities[0]
        result = colorless_ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Mana ability 2: {T}, Pay 1 life: Add one mana of any color.
# ---------------------------------------------------------------------------


class TestAnyColorManaAbility:
    """The second mana ability taps and pays 1 life for any color mana."""

    def test_has_any_color_mana_ability(self) -> None:
        """get_mana_abilities should include a second ability for any color."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_any_color_ability_taps_and_pays_life(self) -> None:
        """Activating the any-color ability should tap the land and cost 1 life."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        starting_life = p1.life

        abilities = card.get_mana_abilities()
        any_color_ability = abilities[1]
        result = any_color_ability.cost(game, card)
        assert result is True
        assert card.is_tapped is True
        assert p1.life == starting_life - 1

    def test_any_color_ability_produces_colored_mana(self) -> None:
        """The any-color ability should add one mana of a chosen color."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)

        abilities = card.get_mana_abilities()
        any_color_ability = abilities[1]
        any_color_ability.cost(game, card)
        # Produce mana (the player chooses a color)
        any_color_ability.mana_produced(game)
        # At least one colored mana should have been added
        total = p1.mana_pool.total()
        assert total >= 1

    def test_any_color_ability_fails_when_tapped(self) -> None:
        """Cannot activate if the land is already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True
        game.get_battlefield(p1).add(card)

        abilities = card.get_mana_abilities()
        any_color_ability = abilities[1]
        result = any_color_ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Activated ability: {5}: Animate to 2/4 Wizard creature
# ---------------------------------------------------------------------------


class TestAnimateAbility:
    """The {5} ability turns the land into a 2/4 Wizard creature (still a land)."""

    def test_has_activated_ability(self) -> None:
        """get_activated_abilities should include the animate ability."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        assert any(isinstance(a, ActivatedAbility) for a in abilities)

    def test_animate_makes_creature(self) -> None:
        """After activation, the land should have the CREATURE card type."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]
        animate_ability.cost(game, card)
        animate_ability.effect(game)

        assert CardType.CREATURE in card.card_types

    def test_animate_still_land(self) -> None:
        """After animation, the card should still be a land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]
        animate_ability.cost(game, card)
        animate_ability.effect(game)

        assert CardType.LAND in card.card_types

    def test_animate_power_toughness(self) -> None:
        """Animated land should be a 2/4."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]
        animate_ability.cost(game, card)
        animate_ability.effect(game)

        assert card.base_power == 2 or getattr(card, "power", None) == 2
        assert card.base_toughness == 4 or getattr(card, "toughness", None) == 4

    def test_animate_wizard_subtype(self) -> None:
        """Animated land should have the Wizard subtype."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]
        animate_ability.cost(game, card)
        animate_ability.effect(game)

        assert "Wizard" in card.subtypes

    def test_animate_does_nothing_if_already_creature(self) -> None:
        """If the land is already a creature, the ability should not re-animate."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})

        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]

        # Animate the first time
        animate_ability.cost(game, card)
        animate_ability.effect(game)
        assert CardType.CREATURE in card.card_types

        # Pre-set creature card type - try to animate again
        # The "if this land isn't a creature" condition should prevent changes
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        power_before = getattr(card, "base_power", None) or getattr(card, "power", None)
        animate_ability.cost(game, card)
        animate_ability.effect(game)
        power_after = getattr(card, "base_power", None) or getattr(card, "power", None)
        # Should remain the same
        assert power_after == power_before


# ---------------------------------------------------------------------------
# Triggered ability: Whenever you cast an instant or sorcery spell,
# this creature gets +1/+0 until end of turn
# ---------------------------------------------------------------------------


class TestAnimateTriggeredAbility:
    """After animation, casting an instant or sorcery gives +1/+0."""

    def _animate_card(self, game, card):
        """Helper to activate the animate ability."""
        abilities = card.get_activated_abilities()
        animate_ability = abilities[0]
        animate_ability.cost(game, card)
        animate_ability.effect(game)

    def test_animate_registers_trigger(self) -> None:
        """After animation, a SpellCastTriggeredEvent trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)

        # Check that a trigger for SpellCastTriggeredEvent is registered
        triggers = game.trigger_manager.get_triggers_for_source(card)
        spell_cast_triggers = [
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        ]
        assert len(spell_cast_triggers) >= 1

    def test_trigger_fires_for_instant(self) -> None:
        """Casting an instant should fire the trigger and grant +1/+0."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)
        base_power = getattr(card, "power", None) or getattr(card, "base_power", 2)

        # Simulate casting an instant by firing the event
        from engine.card import Instant
        spell = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=spell, player=p1, card=spell, controller=p1
        )
        game.trigger_manager.fire_event(game, event)

        # The trigger should push something onto the stack
        assert len(game.stack) >= 1

        # Resolve the trigger
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        # Card should have +1/+0
        new_power = getattr(card, "power", None) or getattr(card, "modified_power", None)
        assert new_power is not None
        assert new_power >= base_power + 1

    def test_trigger_fires_for_sorcery(self) -> None:
        """Casting a sorcery should also fire the trigger."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)
        base_power = getattr(card, "power", None) or getattr(card, "base_power", 2)

        from engine.card import Sorcery
        spell = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=spell, player=p1, card=spell, controller=p1
        )
        game.trigger_manager.fire_event(game, event)

        assert len(game.stack) >= 1
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        new_power = getattr(card, "power", None) or getattr(card, "modified_power", None)
        assert new_power is not None
        assert new_power >= base_power + 1

    def test_trigger_does_not_fire_for_creature_spell(self) -> None:
        """Casting a creature spell should NOT fire the trigger."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)

        from engine.card import Creature
        creature_spell = Creature(
            name="Test Creature", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        event = SpellCastTriggeredEvent(
            spell=creature_spell, player=p1, card=creature_spell, controller=p1
        )
        stack_len_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        # No new stack object for the creature spell
        assert len(game.stack) == stack_len_before

    def test_trigger_stacks_multiple_casts(self) -> None:
        """Multiple instant/sorcery casts should each give +1/+0."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)
        base_power = getattr(card, "power", None) or getattr(card, "base_power", 2)

        from engine.card import Instant
        # Cast two instants
        for i in range(2):
            spell = Instant(name=f"Test Instant {i}", owner=p1, controller=p1)
            event = SpellCastTriggeredEvent(
                spell=spell, player=p1, card=spell, controller=p1
            )
            game.trigger_manager.fire_event(game, event)
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        new_power = getattr(card, "power", None) or getattr(card, "modified_power", None)
        assert new_power is not None
        assert new_power >= base_power + 2

    def test_trigger_only_fires_for_controllers_spells(self) -> None:
        """The trigger should only fire for spells cast by the land's controller."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        self._animate_card(game, card)

        from engine.card import Instant
        # Opponent casts a spell
        opponent_spell = Instant(name="Opponent Spell", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(
            spell=opponent_spell, player=p2, card=opponent_spell, controller=p2
        )
        stack_len_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        # Should not fire for opponent's spell
        assert len(game.stack) == stack_len_before
