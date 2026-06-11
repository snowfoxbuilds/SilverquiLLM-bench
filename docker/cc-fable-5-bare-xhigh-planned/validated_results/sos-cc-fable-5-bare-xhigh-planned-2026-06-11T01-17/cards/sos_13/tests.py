"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"


def _bears(n: int) -> list[Creature]:
    return [Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
            for i in range(n)]


def _cast_emeritus(game, token_to_player) -> EmeritusOfTruceSwordsToPlowshares:
    card = EmeritusOfTruceSwordsToPlowshares(owner=None)
    set_board_state(game, 0, hand=[card],
                    mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
    game.players[0]._script.append(token_to_player)  # ETB: target player
    cast_spell(game, 0, FULL_NAME)
    return card


class TestEmeritusProperties:
    def test_static_data(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == FULL_NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.prepared is False


class TestEmeritusEnters:
    def test_etb_creates_inkling_for_target_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _cast_emeritus(game, p1)
        inklings = [c for c in game.get_battlefield(p1).get_all()
                    if getattr(c, "name", "") == "Inkling"]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token
        assert "Inkling" in token.subtypes

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p2 = game.players[1]
        set_board_state(game, 1, battlefield=_bears(2))
        # Token to the opponent: they end at 3 creatures vs my 1.
        card = _cast_emeritus(game, p2)
        assert card.prepared is True

    def test_not_prepared_when_opponent_does_not_have_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Token to me: I end at 2 creatures vs opponent's 0.
        card = _cast_emeritus(game, p1)
        assert card.prepared is False


class TestPreparedCast:
    def _prepared_emeritus(self, game):
        set_board_state(game, 1, battlefield=_bears(2))
        return _cast_emeritus(game, game.players[1])

    def test_cast_copy_exiles_creature_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = self._prepared_emeritus(game)
        bear = next(c for c in game.get_battlefield(p2).get_all()
                    if c.name == "Bear 0")
        set_board_state(game, 0, life=20, mana={ManaType.WHITE: 1})
        # Consumed: bear (the Swords target), then priority passes.
        p1._script.extend([bear, "pass"])
        p2._script.extend(["pass"])
        assert card.cast_prepared_copy(game) is True
        priority_loop(game)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 22  # bear's controller gains its power (2)
        assert card.prepared is False
        assert p1.mana_pool.get(ManaType.WHITE) == 0  # {W} was paid
        # The resolved copy ceases to exist (no Swords card in any graveyard).
        assert not any(getattr(c, "name", "") == "Swords to Plowshares"
                       for c in game.get_graveyard(p1).get_all())

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _cast_emeritus(game, p1)  # not prepared
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        assert card.cast_prepared_copy(game) is False

    def test_cannot_cast_without_mana(self) -> None:
        game = create_game()
        card = self._prepared_emeritus(game)
        set_board_state(game, 0, mana={})
        assert card.cast_prepared_copy(game) is False
        assert card.prepared is True  # still prepared

    def test_second_cast_fails_after_unprepare(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = self._prepared_emeritus(game)
        bear = next(c for c in game.get_battlefield(p2).get_all()
                    if c.name == "Bear 0")
        set_board_state(game, 0, mana={ManaType.WHITE: 2})
        p1._script.extend([bear, "pass"])
        p2._script.extend(["pass"])
        assert card.cast_prepared_copy(game) is True
        priority_loop(game)
        assert card.cast_prepared_copy(game) is False  # unprepared now
