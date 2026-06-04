"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land
from engine.casting import resolve_top
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestProperties:
    def test_basics(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert c.name == "Great Hall of the Biblioplex"
        assert isinstance(c, Land)
        assert CardType.LAND in c.card_types
        # Not a creature until animated.
        assert CardType.CREATURE not in c.card_types


class TestManaAbilities:
    def test_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        colorless = hall.get_mana_abilities()[0]
        assert colorless.cost(game, hall) is True
        colorless.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True
        # Cannot tap again.
        assert colorless.cost(game, hall) is False

    def test_any_color_pays_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        any_color = hall.get_mana_abilities()[1]
        p1._script.append(ManaType.RED)  # choose color
        assert any_color.cost(game, hall) is True
        any_color.mana_produced(game)
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_any_color_blocked_without_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], life=0)
        any_color = hall.get_mana_abilities()[1]
        assert any_color.cost(game, hall) is False


class TestAnimate:
    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5}
        )
        return game, p1, hall

    def test_becomes_creature(self) -> None:
        game, p1, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4

    def test_pump_on_instant_cast(self) -> None:
        game, p1, hall = self._setup()
        hall.get_activated_abilities()[0].effect(game)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = p1
        bolt.controller = p1
        spell_obj = StackObject(source=bolt, controller=p1)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_obj, card=bolt, controller=p1, player=p1
            ),
        )
        resolve_top(game)  # resolve the pump trigger
        assert hall.power == 3
        assert hall.toughness == 4

    def test_animate_idempotent(self) -> None:
        game, p1, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.effect(game)
        # Already a creature — a second activation is a no-op on P/T.
        ability.effect(game)
        assert hall.power == 2 and hall.toughness == 4
