"""Tests for Emeritus of Truce // Swords to Plowshares (SOS 13)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from test_utils import card_colors, create_game, set_board_state


def _bear(name: str = "Bear", controller: Any = None) -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2)
    if controller is not None:
        c.owner = controller
        c.controller = controller
    return c


def _inklings(player: Any) -> list:
    return [
        o
        for o in player.zones[Zone.BATTLEFIELD].get_all()
        if "Inkling" in getattr(o, "subtypes", set())
    ]


class TestEmeritusProperties:
    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).name == "Emeritus of Truce"

    def test_mana_cost(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).mana_cost
            == ManaCost.parse("{1}{W}{W}")
        )

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.power == 3
        assert card.toughness == 3

    def test_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_white(self) -> None:
        assert card_colors(EmeritusOfTruceSwordsToPlowshares(owner=None)) == {"W"}

    def test_starts_unprepared(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).is_prepared is False


class TestSwordsToPlowshares:
    def test_is_instant(self) -> None:
        card = SwordsToPlowshares(owner=None)
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        assert SwordsToPlowshares(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_targets_a_creature(self) -> None:
        game = create_game()
        reqs = SwordsToPlowshares(owner=None).get_targets(game)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        bear = _bear()
        assert reqs[0].filter_fn(bear) is True
        assert reqs[0].filter_fn(game.players[0]) is False

    def test_exiles_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = _bear(controller=p2)
        set_board_state(game, 1, battlefield=[bear], life=20)
        stp = SwordsToPlowshares(owner=p1, controller=p1)
        stp.chosen_targets = [bear]
        stp.on_resolve(game)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p2.zones[Zone.EXILE].contains(bear)
        assert p2.life == 22  # gained life equal to bear's power


class TestEmeritusETB:
    def _fire_etb(self, game, emeritus, target_player):
        emeritus.register_triggers(game)
        emeritus.chosen_targets = [target_player]
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=emeritus, controller=emeritus.controller
            ),
        )
        # Resolve the ETB trigger that was pushed.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

    def test_creates_inkling_for_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        self._fire_etb(game, emeritus, p2)
        assert len(_inklings(p2)) == 1
        token = _inklings(p2)[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords

    def test_becomes_prepared_when_opponent_has_more(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(
            game, 1, battlefield=[_bear("a"), _bear("b"), _bear("c"), _bear("d")]
        )
        self._fire_etb(game, emeritus, p1)
        # p1: emeritus + inkling = 2 ; p2: 4 -> prepared.
        assert emeritus.is_prepared is True

    def test_not_prepared_when_you_have_more(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus, _bear("x"), _bear("y")])
        self._fire_etb(game, emeritus, p1)
        # p2 has no creatures -> not prepared.
        assert emeritus.is_prepared is False

    def test_defaults_target_to_controller(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)
        # No chosen target set.
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert len(_inklings(p1)) == 1


class TestPreparedMechanic:
    def test_cast_prepared_copy_when_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        bear = _bear(controller=p2)
        set_board_state(game, 1, battlefield=[bear], life=20)
        emeritus.is_prepared = True

        result = emeritus.cast_prepared_copy(game, bear)
        assert result is True
        assert p2.zones[Zone.EXILE].contains(bear)
        assert p2.life == 22
        assert emeritus.is_prepared is False  # unprepared after casting

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        bear = _bear(controller=p2)
        set_board_state(game, 1, battlefield=[bear], life=20)
        emeritus.is_prepared = False

        result = emeritus.cast_prepared_copy(game, bear)
        assert result is False
        assert p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p2.life == 20
