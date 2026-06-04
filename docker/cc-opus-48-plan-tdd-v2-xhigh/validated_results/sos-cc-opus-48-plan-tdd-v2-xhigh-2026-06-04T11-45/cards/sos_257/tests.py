"""Tests for SOS 257 — Great Hall of the Biblioplex (manland)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _sorc(name: str = "Bolt") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{R}"))


def _drain(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestHallProperties:
    def test_name(self) -> None:
        assert (
            GreatHallOfTheBiblioplex(owner=None).name
            == "Great Hall of the Biblioplex"
        )

    def test_is_land(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in c.card_types
        assert CardType.CREATURE not in c.card_types

    def test_not_attacker_until_animated(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert not hasattr(c, "base_power")


class TestHallMana:
    def test_taps_for_colorless(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True
        # Already tapped → cost fails.
        assert ability.cost(game, hall) is False

    def test_any_color_for_one_life(self) -> None:
        game = create_game(scripts=([ManaType.GREEN], []))
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        assert hall.is_tapped is True


class TestHallAnimation:
    def _animate(self, game: Any, hall: Any, p1: Any) -> None:
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)

    def test_five_makes_2_4_wizard_creature(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        self._animate(game, hall, p1)
        assert hall._is_animated is True
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types          # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert hasattr(hall, "base_power")               # now a legal attacker

    def test_cannot_animate_without_mana(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 4})
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is False
        assert getattr(hall, "_is_animated", False) is False

    def test_animation_survives_apply_all(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        self._animate(game, hall, p1)
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE in hall.card_types
        assert hall.power == 2 and hall.toughness == 4


class TestHallPump:
    def _animate(self, game: Any, hall: Any) -> None:
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        ab = hall.get_activated_abilities()[0]
        ab.cost(game, hall)
        ab.effect(game)

    def test_pump_on_instant_sorcery_cast(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        hall.register_triggers(game)
        self._animate(game, hall)

        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=None, player=p1, card=_sorc())
        )
        _drain(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3 and hall.toughness == 4

        # Second cast stacks another +1/+0.
        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=None, player=p1, card=_sorc())
        )
        _drain(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 4

        # End of turn → pump expires.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2

    def test_no_pump_when_not_animated(self) -> None:
        game = create_game()
        p1, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        hall.register_triggers(game)

        game.trigger_manager.fire_event(
            game, SpellCastTriggeredEvent(spell=None, player=p1, card=_sorc())
        )
        assert game.stack.is_empty()
