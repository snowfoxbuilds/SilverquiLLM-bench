"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.casting import CastingError
from engine.stack import priority_loop
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


def _cast_emeritus(game, target_player):
    """Cast Emeritus from p1's hand; the ETB targets *target_player*."""
    p1 = game.players[0]
    em = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(
        game, 0, hand=[em],
        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1},
    )
    p1._script.extend([target_player])
    cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
    return em


class TestProperties:
    def test_static_data(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.prepared is False


class TestEnterTrigger:
    def test_target_player_creates_inkling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        em = _cast_emeritus(game, p1)
        inklings = [
            c for c in game.get_battlefield(p1).get_all()
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token
        assert "Inkling" in token.subtypes
        # p1 has Emeritus + token (2) vs 0 — not prepared.
        assert em.prepared is False
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        em = _cast_emeritus(game, p2)  # token goes to the opponent
        assert game.get_battlefield(p2).get_all()[-1].name == "Inkling"
        # p2: 3 bears + Inkling = 4 > p1: just Emeritus = 1 → prepared.
        assert em.prepared is True
        copies = [
            c for c in p1.zones[Zone.EXILE].get_all()
            if getattr(c, "name", "") == "Swords to Plowshares"
        ]
        assert len(copies) == 1


class TestPreparedCast:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        em = _cast_emeritus(game, p2)
        assert em.prepared
        return game, em

    def test_cast_copy_exiles_creature_and_unprepares(self) -> None:
        game, em = self._prepared_setup()
        p1, p2 = game.players
        bear = game.get_battlefield(p2).get_all()[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p1._script.extend([bear, "pass"])
        p2._script.extend(["pass"])
        em.cast_prepared_spell(game)
        priority_loop(game)
        assert p2.zones[Zone.EXILE].contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert p2.life == 22  # gains life equal to the bear's power
        assert em.prepared is False
        # The copy ceased to exist — neither graveyard nor exile holds it.
        assert not any(
            getattr(c, "name", "") == "Swords to Plowshares"
            for c in p1.zones[Zone.GRAVEYARD].get_all()
        )
        assert not any(
            getattr(c, "name", "") == "Swords to Plowshares"
            for c in p1.zones[Zone.EXILE].get_all()
        )

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        em = _cast_emeritus(game, p1)  # not prepared
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        with pytest.raises(CastingError):
            em.cast_prepared_spell(game)

    def test_cost_w_must_be_paid(self) -> None:
        game, em = self._prepared_setup()
        p1 = game.players[0]
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})  # no {W}
        with pytest.raises(CastingError):
            em.cast_prepared_spell(game)
        assert em.prepared is True  # still prepared

    def test_copy_removed_if_emeritus_dies_prepared(self) -> None:
        game, em = self._prepared_setup()
        p1, p2 = game.players
        from engine.game import destroy

        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        destroy(game, em)
        priority_loop(game)  # resolve the leaves-battlefield cleanup
        assert p1.zones[Zone.GRAVEYARD].contains(em)
        assert not any(
            getattr(c, "name", "") == "Swords to Plowshares"
            for c in p1.zones[Zone.EXILE].get_all()
        )
        assert em.prepared is False
