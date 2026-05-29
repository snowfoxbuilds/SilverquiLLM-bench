"""Tests for sos_257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaType, ManaCost, Zone
from test_utils import create_game


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        assert CardType.LAND in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_is_not_initially_creature(self) -> None:
        assert CardType.CREATURE not in GreatHallOfTheBiblioplex(owner=None).card_types

    def test_no_mana_cost(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert hall.mana_cost is None or hall.mana_cost.cmc == 0


class TestGreatHallManaAbilities:
    def test_has_two_mana_abilities(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert len(hall.get_mana_abilities()) == 2

    def test_tap_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        abilities = hall.get_mana_abilities()
        # First ability: {T}: Add {C}
        tap_ability = abilities[0]
        assert not hall.is_tapped
        result = tap_ability.cost(game, hall)
        assert result is True
        assert hall.is_tapped
        tap_ability.mana_produced(game)
        assert p1.mana_pool._pool[ManaType.COLORLESS] > 0

    def test_tap_already_tapped_fails(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = True
        abilities = hall.get_mana_abilities()
        result = abilities[0].cost(game, hall)
        assert result is False

    def test_second_ability_requires_tap_and_life(self) -> None:
        """T + pay 1 life: add one mana of any color (restricted to instant/sorcery)."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        abilities = hall.get_mana_abilities()
        colored_ability = abilities[1]

        initial_life = p1.life
        # Activate the life-cost ability
        result = colored_ability.cost(game, hall)
        assert result is True
        assert hall.is_tapped
        assert p1.life == initial_life - 1
        # Add colored mana (any color — implementation may add any)
        p1._script.appendleft(ManaType.WHITE)  # choose White
        colored_ability.mana_produced(game)
        total_mana = sum(
            p1.mana_pool._pool[mt]
            for mt in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN)
        )
        assert total_mana >= 1


class TestGreatHallCreatureTransformation:
    """The {5} ability turns the land into a 2/4 Wizard creature."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        abilities = hall.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_becomes_creature_when_activated(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)

        # Give player 5 mana
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        abilities = hall.get_activated_abilities(game)
        assert len(abilities) >= 1
        ability = abilities[0]
        result = ability.cost(game, hall)
        assert result is True
        ability.effect(game)

        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert CardType.LAND in hall.card_types  # still a land

    def test_creature_is_two_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)

        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = hall.get_activated_abilities(game)[0]
        ability.cost(game, hall)
        ability.effect(game)

        assert hall.base_power == 2
        assert hall.base_toughness == 4

    def test_cannot_activate_twice(self) -> None:
        """If already a creature, {5} doesn't apply."""
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)

        p1.mana_pool.add(ManaType.COLORLESS, 10)
        ability = hall.get_activated_abilities(game)[0]
        ability.cost(game, hall)
        ability.effect(game)
        # Now it's a creature — second activation should fail
        result = ability.cost(game, hall)
        assert result is False

    def test_insufficient_mana_fails(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)

        p1.mana_pool.add(ManaType.COLORLESS, 4)  # only 4, needs 5
        ability = hall.get_activated_abilities(game)[0]
        result = ability.cost(game, hall)
        assert result is False


class TestGreatHallWizardTrigger:
    """When creature, whenever you cast an instant/sorcery, it gets +1/+0 until EOT."""

    def _become_creature(self, game, p1, hall):
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = hall.get_activated_abilities(game)[0]
        ability.cost(game, hall)
        ability.effect(game)
        hall.register_triggers(game)

    def test_trigger_registers_after_transformation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        self._become_creature(game, p1, hall)
        triggers = game.trigger_manager.get_triggers_for_source(hall)
        assert len(triggers) >= 1

    def test_power_increases_on_spell_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        self._become_creature(game, p1, hall)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        from engine.stack import StackObject
        stack_obj = StackObject(
            source=instant, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )

        initial_power = hall.modified_power
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )

        # Resolve the trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert hall.modified_power == initial_power + 1

    def test_no_boost_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        self._become_creature(game, p1, hall)

        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        from engine.stack import StackObject
        stack_obj = StackObject(source=creature, controller=p1, targets=[],
                                on_resolve=lambda g: None)
        initial_power = hall.modified_power
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=creature, controller=p1),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert hall.modified_power == initial_power  # no boost

    def test_boost_resets_at_eot(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hall)
        self._become_creature(game, p1, hall)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        from engine.stack import StackObject
        stack_obj = StackObject(
            source=instant, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=stack_obj, player=p1, card=instant, controller=p1),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert hall.modified_power > 2

        # Simulate EOT cleanup: _reset_characteristics resets modified_power
        hall._reset_characteristics()

        # Power should be back to base
        assert hall.modified_power == 2
