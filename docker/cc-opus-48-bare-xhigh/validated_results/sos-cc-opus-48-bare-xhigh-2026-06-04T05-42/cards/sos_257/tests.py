"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _hall(game, player):
    hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
    set_board_state(game, game.players.index(player), battlefield=[hall])
    return hall


class TestProperties:
    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert (
            GreatHallOfTheBiblioplex(owner=None).name
            == "Great Hall of the Biblioplex"
        )

    def test_no_mana_cost(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()

    def test_cannot_be_cast(self) -> None:
        game = create_game()
        assert GreatHallOfTheBiblioplex(owner=None).can_cast(game) is False

    def test_not_animated_by_default(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None)._is_animated is False

    def test_zero_power_toughness_before_animation(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert (hall.power, hall.toughness) == (0, 0)


class TestColorlessMana:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall(game, p1)
        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_tap_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall(game, p1)
        hall.is_tapped = True
        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is False


class TestAnyColorMana:
    def test_pay_life_for_chosen_color(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1 = game.players[0]
        hall = _hall(game, p1)
        p1.life = 20
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        assert hall.is_tapped is True
        assert p1.life == 19
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.GREEN) == 1

    def test_fails_at_zero_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall(game, p1)
        p1.life = 0
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is False
        assert hall.is_tapped is False


class TestAnimate:
    def _animate(self, game, p1):
        hall = _hall(game, p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        return hall

    def test_becomes_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._animate(game, p1)
        assert hall._is_animated is True
        assert CardType.CREATURE in hall.card_types

    def test_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._animate(game, p1)
        assert CardType.LAND in hall.card_types

    def test_is_two_four_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._animate(game, p1)
        assert (hall.power, hall.toughness) == (2, 4)
        assert "Wizard" in hall.subtypes

    def test_animate_costs_five_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall(game, p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 4})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is False

    def test_animate_is_idempotent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._animate(game, p1)
        # Re-running the effect does not stack a second animation.
        hall.get_activated_abilities()[0].effect(game)
        assert (hall.power, hall.toughness) == (2, 4)


class TestPump:
    def _setup(self, game, p1):
        hall = _hall(game, p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.get_activated_abilities()[0].cost(game, hall)
        hall.get_activated_abilities()[0].effect(game)
        return hall

    def _cast(self, game, p1, hall, name="Bolt"):
        spell = Instant(name=name)
        spell.owner = p1
        spell.controller = p1
        spell_obj = StackObject(source=spell, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, player=p1, card=spell, controller=p1
            ),
        )
        # Resolve the pump trigger sitting on the stack.
        trig = game.stack.pop()
        trig.on_resolve(game)

    def test_pump_on_instant_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._setup(game, p1)
        self._cast(game, p1, hall)
        assert hall.power == 3

    def test_pump_stacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._setup(game, p1)
        self._cast(game, p1, hall, "Bolt1")
        self._cast(game, p1, hall, "Bolt2")
        assert hall.power == 4

    def test_pump_resets_at_cleanup(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = self._setup(game, p1)
        self._cast(game, p1, hall)
        assert hall.power == 3
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2

    def test_no_pump_when_not_animated(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = _hall(game, p1)
        # No animation: there is no pump trigger registered.
        assert game.trigger_manager.get_triggers_for_source(hall) == []
