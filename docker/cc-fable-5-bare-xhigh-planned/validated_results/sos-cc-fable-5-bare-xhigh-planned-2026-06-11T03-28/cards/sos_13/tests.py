"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


def _bears(n: int, prefix: str = "Bear") -> list[Creature]:
    return [
        Creature(name=f"{prefix} {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


def _cast_emeritus(game, target_player):
    p1 = game.players[0]
    card = EmeritusOfTruceSwordsToPlowshares(owner=p1)
    game.get_hand(p1).add(card)
    card.owner = card.controller = p1
    p1.mana_pool.add(ManaType.COLORLESS, 1)
    p1.mana_pool.add(ManaType.WHITE, 2)
    p1._script.extend([target_player])  # ETB target player choice
    cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
    return card


class TestEmeritusProperties:
    def test_constructs_bare_with_full_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.is_prepared is False


class TestEmeritusEnterTrigger:
    def test_target_player_creates_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _cast_emeritus(game, p2)
        inklings = [
            c for c in game.get_battlefield(p2).get_all()
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_not_prepared_when_opponent_not_ahead(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Token goes to p1: p1 then has Emeritus + Inkling = 2, p2 has 0.
        card = _cast_emeritus(game, p1)
        assert card.is_prepared is False

    def test_prepared_when_opponent_controls_more(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        # Token to p2: p2 has 3 creatures, p1 has just Emeritus.
        card = _cast_emeritus(game, p2)
        assert card.is_prepared is True
        swords = [
            c for c in game.get_exile(p1).get_all()
            if getattr(c, "name", "") == "Swords to Plowshares"
        ]
        assert len(swords) == 1

    def test_tie_is_not_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(1))
        # Token to p2: p2 has 2 creatures, p1 has Emeritus + ... 1 vs 2?
        # p1: Emeritus (1). p2: bear + Inkling (2) → 2 > 1 → prepared.
        # For a true tie give p1 a bear as well.
        set_board_state(game, 0, battlefield=_bears(1, "Mine"))
        card = _cast_emeritus(game, p2)
        # p1: Mine + Emeritus = 2; p2: bear + Inkling = 2 → tie, not prepared.
        assert card.is_prepared is False


class TestPreparedCast:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        card = _cast_emeritus(game, p2)
        assert card.is_prepared
        return game, p1, p2, card

    def test_cast_copy_exiles_creature_and_unprepares(self) -> None:
        game, p1, p2, card = self._prepared_setup()
        bear = next(
            c for c in game.get_battlefield(p2).get_all()
            if c.name == "Bear 0"
        )
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.extend([bear])  # Swords target
        card.cast_prepared_spell(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 22  # gained life equal to the bear's power
        assert card.is_prepared is False

    def test_cannot_cast_without_paying_w(self) -> None:
        from engine.casting import CastingError

        game, p1, p2, card = self._prepared_setup()
        try:
            card.cast_prepared_spell(game)
            raised = False
        except CastingError:
            raised = True
        assert raised
        assert card.is_prepared is True

    def test_cannot_cast_twice(self) -> None:
        from engine.casting import CastingError

        game, p1, p2, card = self._prepared_setup()
        bear = next(
            c for c in game.get_battlefield(p2).get_all()
            if c.name == "Bear 0"
        )
        p1.mana_pool.add(ManaType.WHITE, 2)
        p1._script.extend([bear])
        card.cast_prepared_spell(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        try:
            card.cast_prepared_spell(game)
            raised = False
        except CastingError:
            raised = True
        assert raised
