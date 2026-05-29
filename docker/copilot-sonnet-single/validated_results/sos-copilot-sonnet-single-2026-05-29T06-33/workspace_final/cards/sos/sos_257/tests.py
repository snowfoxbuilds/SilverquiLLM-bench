"""Tests for Great Hall of the Biblioplex (SOS 257).

Card spec:
  Name: Great Hall of the Biblioplex
  Mana cost: (none)
  Type: Land
  Oracle:
    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      'Whenever you cast an instant or sorcery spell, this creature gets
      +1/+0 until end of turn.' It's still a land.

Tests cover:
  - Static properties (name, type, no mana cost, Land instance)
  - First mana ability: {T} → Add {C}
  - Second mana ability: {T}, Pay 1 life → Add one colored mana, life decremented
  - Second mana ability: cannot activate if tapped
  - Third ability: {5} → becomes 2/4 Wizard creature (still a land) if not creature
  - Third ability: power=2, toughness=4 after transformation
  - Third ability: Wizard subtype added on transformation
  - Third ability: still has CardType.LAND after transformation
  - Third ability: has CardType.CREATURE after transformation
  - Idempotency: if already a creature, {5} ability does NOT change base stats again
  - Triggered ability: on_resolve registers SpellCastTriggeredEvent trigger
  - Triggered ability: casting an instant fires +1/+0 pump
  - Triggered ability: casting a sorcery fires +1/+0 pump
  - Triggered ability: casting a non-instant/sorcery does NOT pump
  - get_mana_abilities returns at least 2 abilities
  - get_activated_abilities returns at least 1 ability (the {5} ability)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data must match the SOS 257 spec."""

    def test_is_land_instance(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost; mana_cost should be empty."""
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.mana_cost == ManaCost()

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_not_initially_a_creature(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_is_tapped_initially_false(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.is_tapped is False


# ---------------------------------------------------------------------------
# Mana abilities
# ---------------------------------------------------------------------------


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Land mana abilities: {T}→{C} and {T}+1life→any color."""

    def test_has_at_least_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 2

    def test_tap_for_colorless_adds_colorless_mana(self) -> None:
        """First ability: {T} → add {C} to controller's mana pool."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        abilities = land.get_mana_abilities()
        # Find the colorless mana ability (tap-only, no life cost)
        # Activate the first ability (should be the {T}: Add {C} one)
        colorless_ability = abilities[0]
        assert not land.is_tapped
        colorless_ability.cost(game, land)
        colorless_ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 1, (
            "{T}: Add {C} should add exactly 1 colorless mana"
        )

    def test_tap_for_colorless_taps_the_land(self) -> None:
        """Activating the first mana ability should tap the land."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        ability = land.get_mana_abilities()[0]
        ability.cost(game, land)
        assert land.is_tapped, "Land should be tapped after activating {T}: Add {C}"

    def test_colorless_ability_fails_if_already_tapped(self) -> None:
        """A tapped land cannot activate {T}: Add {C}."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.is_tapped = True
        set_board_state(game, 0, battlefield=[land])

        ability = land.get_mana_abilities()[0]
        result = ability.cost(game, land)
        assert result is False, "Tapped land should not be able to pay {T} cost"

    def test_colored_mana_ability_costs_one_life(self) -> None:
        """{T}, Pay 1 life: should deduct 1 life from the controller."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20)

        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]  # Second ability: {T}, Pay 1 life

        colored_ability.cost(game, land)
        colored_ability.mana_produced(game)

        assert p1.life == 19, (
            "{T}, Pay 1 life should deduct exactly 1 life from the controller"
        )

    def test_colored_mana_ability_adds_colored_mana(self) -> None:
        """{T}, Pay 1 life: should add one mana to controller's pool."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20)

        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]

        # Pay cost (tap + 1 life) then produce mana
        colored_ability.cost(game, land)
        colored_ability.mana_produced(game)

        # Should have added at least 1 mana of some color to the pool
        total_mana = p1.mana_pool.total()
        assert total_mana >= 1, (
            "{T}, Pay 1 life should add at least 1 mana to the controller's pool"
        )

    def test_colored_mana_ability_adds_non_colorless_mana(self) -> None:
        """{T}, Pay 1 life: the mana produced should be a color, not colorless."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20)

        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]

        colored_ability.cost(game, land)
        # Script a color choice for DeterministicPlayer if needed
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(ManaType.BLUE)

        colored_ability.mana_produced(game)

        # The colorless pool should NOT have increased (the mana is colored)
        # The total mana in colored slots should be >= 1
        colored_total = sum(
            p1.mana_pool.get(mt)
            for mt in [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]
        )
        assert colored_total >= 1, (
            "{T}, Pay 1 life should produce colored mana (not colorless)"
        )

    def test_colored_ability_taps_land(self) -> None:
        """{T}, Pay 1 life cost should tap the land."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20)

        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]
        colored_ability.cost(game, land)

        assert land.is_tapped, "Land should be tapped after paying {T}, Pay 1 life cost"

    def test_colored_ability_fails_if_tapped(self) -> None:
        """If the land is already tapped, {T}, Pay 1 life cost should fail."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.is_tapped = True
        set_board_state(game, 0, battlefield=[land], life=20)

        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]
        result = colored_ability.cost(game, land)
        assert result is False, "Tapped land cannot pay {T} for colored mana ability"


# ---------------------------------------------------------------------------
# {5}: Creature transformation ability
# ---------------------------------------------------------------------------


class TestGreatHallOfTheBiblioplexCreatureTransformation:
    """{5}: If not already a creature, becomes a 2/4 Wizard creature (still land)."""

    def _activate_five_ability(self, land, game) -> None:
        """Helper: activate the {5} ability (pay cost and apply effect)."""
        abilities = land.get_activated_abilities()
        assert abilities, "Land must have at least one activated ability ({5} ability)"
        five_ability = abilities[0]
        five_ability.cost(game, land)
        five_ability.effect(game)

    def test_has_at_least_one_activated_ability(self) -> None:
        """The land must expose the {5} ability via get_activated_abilities."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_transformation_adds_creature_type(self) -> None:
        """After {5} ability, CardType.CREATURE must be in card_types."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._activate_five_ability(land, game)

        assert CardType.CREATURE in land.card_types, (
            "After {5} activation, the land should become a creature"
        )

    def test_transformation_keeps_land_type(self) -> None:
        """After {5} ability, CardType.LAND must still be in card_types."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._activate_five_ability(land, game)

        assert CardType.LAND in land.card_types, (
            "After {5} activation, the land should still be a land"
        )

    def test_transformation_sets_power_to_2(self) -> None:
        """After {5} ability, base_power should be 2."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._activate_five_ability(land, game)

        assert getattr(land, "base_power", None) == 2, (
            "After transformation, base_power should be 2"
        )

    def test_transformation_sets_toughness_to_4(self) -> None:
        """After {5} ability, base_toughness should be 4."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._activate_five_ability(land, game)

        assert getattr(land, "base_toughness", None) == 4, (
            "After transformation, base_toughness should be 4"
        )

    def test_transformation_adds_wizard_subtype(self) -> None:
        """After {5} ability, 'Wizard' should be in subtypes."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._activate_five_ability(land, game)

        assert "Wizard" in land.subtypes, (
            "After transformation, 'Wizard' should be in subtypes"
        )

    def test_transformation_registers_trigger(self) -> None:
        """After {5} ability, a SpellCastTriggeredEvent trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        triggers_before = len(game.trigger_manager.get_triggers())
        self._activate_five_ability(land, game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after > triggers_before, (
            "After transformation, a SpellCastTriggeredEvent trigger should be registered"
        )

    def test_transformation_not_applied_if_already_creature(self) -> None:
        """If the land is already a creature, {5} should not re-apply the transformation."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 20})

        # First activation — becomes creature with power 2
        self._activate_five_ability(land, game)
        assert CardType.CREATURE in land.card_types

        # Manually bump the land's power to detect if it gets reset
        if hasattr(land, "base_power"):
            land.base_power = 99

        # Second activation — should be a no-op (already a creature)
        self._activate_five_ability(land, game)

        # base_power should remain 99 (not reset to 2)
        assert getattr(land, "base_power", None) == 99, (
            "If already a creature, {5} should not re-apply the transformation "
            "(base_power should remain unchanged)"
        )


# ---------------------------------------------------------------------------
# Triggered ability: +1/+0 when an instant or sorcery is cast
# ---------------------------------------------------------------------------


class TestGreatHallOfTheBiblioplexPumpTrigger:
    """Whenever you cast an instant or sorcery, the creature gets +1/+0 until EOT."""

    def _transform_to_creature(self, land, game) -> None:
        """Activate {5} to turn the land into a creature."""
        abilities = land.get_activated_abilities()
        assert abilities
        five_ability = abilities[0]
        five_ability.cost(game, land)
        five_ability.effect(game)

    def test_casting_instant_fires_pump_trigger(self) -> None:
        """Casting an instant while the land-creature is in play puts a pump trigger on the stack."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._transform_to_creature(land, game)

        # Verify trigger is registered before we fire the event
        triggers = game.trigger_manager.get_triggers()
        assert any(t.event_type is SpellCastTriggeredEvent for t in triggers), (
            "A SpellCastTriggeredEvent trigger must be registered after transformation"
        )

        # Fire a SpellCastTriggeredEvent for an instant
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant,
            player=p1,
            card=instant,
            controller=p1,
        )

        stack_size_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        stack_size_after = len(game.stack)

        assert stack_size_after > stack_size_before, (
            "Casting an instant should push the pump trigger onto the stack"
        )

    def test_casting_sorcery_fires_pump_trigger(self) -> None:
        """Casting a sorcery while the land-creature is in play puts a pump trigger on the stack."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._transform_to_creature(land, game)

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=sorcery,
            player=p1,
            card=sorcery,
            controller=p1,
        )

        stack_size_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        stack_size_after = len(game.stack)

        assert stack_size_after > stack_size_before, (
            "Casting a sorcery should push the pump trigger onto the stack"
        )

    def test_casting_creature_spell_does_not_fire_pump_trigger(self) -> None:
        """Casting a non-instant/sorcery (e.g. creature) should NOT trigger the pump."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._transform_to_creature(land, game)

        creature_spell = Creature(
            name="Test Creature", owner=p1, controller=p1, base_power=2, base_toughness=2
        )
        event = SpellCastTriggeredEvent(
            spell=creature_spell,
            player=p1,
            card=creature_spell,
            controller=p1,
        )

        stack_size_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        stack_size_after = len(game.stack)

        assert stack_size_after == stack_size_before, (
            "Casting a creature spell should NOT trigger the +1/+0 pump"
        )

    def test_pump_trigger_resolves_and_increases_power(self) -> None:
        """When the pump trigger resolves, the creature's modified_power increases by 1."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})

        self._transform_to_creature(land, game)

        # Record initial power
        initial_power = getattr(land, "modified_power", getattr(land, "base_power", 2))

        # Fire the spell cast event for an instant
        instant = Instant(name="Shock", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant,
            player=p1,
            card=instant,
            controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger from the stack
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        current_power = getattr(land, "modified_power", getattr(land, "base_power", 2))
        assert current_power > initial_power, (
            f"After pump trigger resolves, creature power should increase from "
            f"{initial_power} to at least {initial_power + 1}, got {current_power}"
        )

    def test_pump_trigger_not_active_before_transformation(self) -> None:
        """Before {5} activates, casting an instant should NOT push any pump trigger."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        # Land is NOT yet a creature — no trigger should be registered
        instant = Instant(name="Bolt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant,
            player=p1,
            card=instant,
            controller=p1,
        )

        stack_size_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        stack_size_after = len(game.stack)

        assert stack_size_after == stack_size_before, (
            "Without transformation, casting an instant should NOT trigger the pump"
        )
