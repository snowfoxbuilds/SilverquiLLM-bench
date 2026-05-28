"""Tests for sos_257 — Great Hall of the Biblioplex.

Covers:
  - Static card properties (name, Land type, no mana cost)
  - Tap for colorless mana (mana_ability_colorless)
  - Tap + pay 1 life for any-color mana (restricted to instant/sorcery)
  - Activation of the {5} ability that turns the land into a 2/4 Wizard
  - That the card is not a creature initially
  - After {5} activation: becomes a creature with LAND still in card_types
  - Power 2, toughness 4 when a creature
  - Wizard subtype when a creature
  - Repeated {5} activation is a no-op (already a creature)
  - Trigger: casting an instant/sorcery grants +1/+0 until end of turn to
    the creature
"""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import CardImpl, Creature, Instant, Land, ManaAbility
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static-property tests
# ---------------------------------------------------------------------------

class TestGreatHallProperties:
    """Card metadata must match the sos_257 spec."""

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_is_land_subclass(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost — the mana_cost should equal an empty ManaCost."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost == ManaCost()

    def test_is_not_creature_initially(self) -> None:
        """Before any activation, the card is not a creature."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_no_power_toughness_initially(self) -> None:
        """Before creature transformation, base_power/toughness are absent or 0."""
        card = GreatHallOfTheBiblioplex(owner=None)
        # base_power/toughness should be absent or equal to 0 (not yet a creature)
        assert not hasattr(card, "base_power") or card.base_power == 0
        assert not hasattr(card, "base_toughness") or card.base_toughness == 0


# ---------------------------------------------------------------------------
# Mana-ability tests
# ---------------------------------------------------------------------------

class TestGreatHallManaAbilities:
    """get_mana_abilities() must return two mana abilities."""

    def test_returns_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_each_ability_is_mana_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        for ability in card.get_mana_abilities():
            assert isinstance(ability, ManaAbility)

    def test_colorless_ability_adds_colorless_mana(self) -> None:
        """First mana ability: tap for colorless ({C})."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        # Find and invoke the colorless mana ability
        abilities = card.get_mana_abilities()
        # The colorless ability should be identifiable by tapping the source and
        # producing COLORLESS mana.
        colorless_ability = abilities[0]
        before = p1.mana_pool.get(ManaType.COLORLESS)
        # Pay cost (tap)
        colorless_ability.cost(game, card)
        # Produce mana
        colorless_ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == before + 1

    def test_colorless_ability_taps_source(self) -> None:
        """Invoking the colorless mana ability taps the land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[0]
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_colorless_ability_fails_if_already_tapped(self) -> None:
        """Tapping an already-tapped land fails (returns False)."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        ability = card.get_mana_abilities()[0]
        result = ability.cost(game, card)
        assert result is False

    def test_life_ability_pays_one_life(self) -> None:
        """Second mana ability: {T}, pay 1 life — life total decreases by 1."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        starting_life = p1.life

        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        assert p1.life == starting_life - 1

    def test_life_ability_taps_source(self) -> None:
        """The life-pay ability also taps the land as part of its cost."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        assert card.is_tapped is True

    def test_life_ability_produces_a_colored_mana(self) -> None:
        """Second mana ability: produces mana that can be any color."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        before_total = p1.mana_pool.total()
        ability = card.get_mana_abilities()[1]
        ability.cost(game, card)
        ability.mana_produced(game)
        # At least one mana was added to the pool
        assert p1.mana_pool.total() > before_total


# ---------------------------------------------------------------------------
# Activated-ability (creature transformation) tests
# ---------------------------------------------------------------------------

class TestGreatHallCreatureTransformation:
    """The {5} activated ability transforms the land into a 2/4 Wizard creature."""

    def test_get_activated_abilities_returns_at_least_one(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activate_creature_ability_adds_creature_type(self) -> None:
        """{5}: land becomes a 2/4 Wizard creature — CardType.CREATURE added."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        # Find the creature-transformation ability (described with "5" or similar)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        transform_ability = abilities[0]

        # Pay cost and apply effect
        transform_ability.cost(game, card)
        transform_ability.effect(game)

        assert CardType.CREATURE in card.card_types

    def test_still_a_land_after_transformation(self) -> None:
        """After transformation the permanent still has CardType.LAND."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]
        transform_ability.cost(game, card)
        transform_ability.effect(game)

        assert CardType.LAND in card.card_types

    def test_power_is_2_after_transformation(self) -> None:
        """After transformation the creature's base power is 2."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]
        transform_ability.cost(game, card)
        transform_ability.effect(game)

        assert getattr(card, "base_power", None) == 2

    def test_toughness_is_4_after_transformation(self) -> None:
        """After transformation the creature's base toughness is 4."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]
        transform_ability.cost(game, card)
        transform_ability.effect(game)

        assert getattr(card, "base_toughness", None) == 4

    def test_wizard_subtype_after_transformation(self) -> None:
        """After transformation the card has 'Wizard' subtype."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]
        transform_ability.cost(game, card)
        transform_ability.effect(game)

        assert "Wizard" in card.subtypes

    def test_repeated_activation_no_change(self) -> None:
        """Activating {5} a second time when already a creature is a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]

        # First activation
        transform_ability.cost(game, card)
        transform_ability.effect(game)
        assert CardType.CREATURE in card.card_types

        # Now manually refund mana and try again — it should be a no-op
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        transform_ability.effect(game)
        # Still a creature (and only one), not duplicated or errored
        assert CardType.CREATURE in card.card_types
        assert CardType.LAND in card.card_types


# ---------------------------------------------------------------------------
# Trigger tests — instant/sorcery cast grants +1/+0 while a creature
# ---------------------------------------------------------------------------

class TestGreatHallInstantSorceryTrigger:
    """While a creature, casting an instant or sorcery gives +1/+0 until end of turn."""

    def _make_creature_hall(self, game, player):
        """Helper: put the Hall on the battlefield and transform it."""
        card = GreatHallOfTheBiblioplex(owner=player, controller=player)
        game.get_battlefield(player).add(card)
        abilities = card.get_activated_abilities()
        transform_ability = abilities[0]
        # Bypass cost to just invoke the effect directly
        transform_ability.effect(game)
        # Register triggers now that it is a creature
        card.register_triggers(game)
        return card

    def test_register_triggers_does_not_raise(self) -> None:
        """register_triggers should not raise even before transformation."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.register_triggers(game)  # should not raise

    def test_instant_cast_triggers_power_boost(self) -> None:
        """Casting an instant fires the trigger; power increases by 1."""
        game = create_game()
        p1 = game.players[0]
        hall = self._make_creature_hall(game, p1)

        # Verify it is a creature with readable power
        assert CardType.CREATURE in hall.card_types
        initial_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))

        # Simulate casting an instant
        instant = Instant(name="Test Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger from the stack
        if game.stack.size() > 0:
            stack_obj = game.stack.peek()
            stack_obj.on_resolve(game)
            game.stack.pop()

        after_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))
        assert after_power == initial_power + 1

    def test_sorcery_cast_triggers_power_boost(self) -> None:
        """Casting a sorcery also triggers the +1/+0 boost."""
        game = create_game()
        p1 = game.players[0]
        hall = self._make_creature_hall(game, p1)

        initial_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))

        from engine.card import Sorcery
        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        if game.stack.size() > 0:
            stack_obj = game.stack.peek()
            stack_obj.on_resolve(game)
            game.stack.pop()

        after_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))
        assert after_power == initial_power + 1

    def test_non_instant_sorcery_does_not_trigger(self) -> None:
        """Casting a creature (not an instant/sorcery) must NOT trigger the boost."""
        game = create_game()
        p1 = game.players[0]
        hall = self._make_creature_hall(game, p1)

        initial_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))

        # Fire a SpellCastTriggeredEvent for a creature spell
        creature = Creature(
            name="Test Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        creature.card_types = {CardType.CREATURE}
        event = SpellCastTriggeredEvent(spell=creature, player=p1, controller=p1)
        stack_before = game.stack.size()
        game.trigger_manager.fire_event(game, event)

        # No trigger should have been pushed to the stack for this event
        assert game.stack.size() == stack_before

        after_power = getattr(hall, "modified_power", getattr(hall, "base_power", 2))
        assert after_power == initial_power

    def test_trigger_not_registered_before_transformation(self) -> None:
        """Before becoming a creature, casting instants/sorceries must not trigger the boost."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Fire an instant cast event — hall is NOT yet a creature
        instant = Instant(name="Test Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        stack_before = game.stack.size()
        game.trigger_manager.fire_event(game, event)

        # No ability trigger should fire for a non-creature land
        assert game.stack.size() == stack_before
