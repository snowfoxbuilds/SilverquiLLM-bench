"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature, Instant
from engine.casting import CastingError
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"
CAST_MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _bears(n: int, prefix: str = "Bear") -> list[Creature]:
    return [
        Creature(name=f"{prefix}{i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestEmeritusProperties:
    def test_constructs_bare_with_full_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == FULL_NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3 and card.base_toughness == 3
        assert card.is_prepared is False


class TestEnterTheBattlefield:
    def test_target_player_creates_inkling_token(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
            mana=dict(CAST_MANA),
        )
        # ETB: choose p1 as the token's controller.  p1 has 0 other
        # creatures; after the token p0 has 1 vs p1's 1 -> not prepared.
        p0._script.append(p1)
        cast_spell(game, 0, FULL_NAME)

        inklings = [
            c for c in p1.zones[Zone.BATTLEFIELD].get_all()
            if c.name == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert "Inkling" in token.subtypes
        assert token.is_token

    def test_not_prepared_when_opponent_not_ahead(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
            mana=dict(CAST_MANA),
        )
        p0._script.append(p0)  # token to self: p0 has 2, p1 has 0
        cast_spell(game, 0, FULL_NAME)
        emeritus = next(
            c for c in p0.zones[Zone.BATTLEFIELD].get_all()
            if c.name == FULL_NAME
        )
        assert emeritus.is_prepared is False
        assert len(p0.zones[Zone.EXILE]) == 0

    def test_prepared_when_opponent_controls_more(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
            mana=dict(CAST_MANA),
        )
        set_board_state(game, 1, battlefield=_bears(3))
        p0._script.append(p0)  # token to self: p0 has 2, p1 has 3
        cast_spell(game, 0, FULL_NAME)
        emeritus = next(
            c for c in p0.zones[Zone.BATTLEFIELD].get_all()
            if c.name == FULL_NAME
        )
        assert emeritus.is_prepared is True
        # The prepare-spell copy sits in exile (rule 722.3c).
        exiled = p0.zones[Zone.EXILE].get_all()
        assert any(c.name == "Swords to Plowshares" for c in exiled)


class TestPreparedCast:
    def _prepared_game(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
            mana=dict(CAST_MANA),
        )
        set_board_state(game, 1, battlefield=_bears(3))
        p0._script.append(p0)
        cast_spell(game, 0, FULL_NAME)
        emeritus = next(
            c for c in p0.zones[Zone.BATTLEFIELD].get_all()
            if c.name == FULL_NAME
        )
        assert emeritus.is_prepared
        return game, emeritus

    def test_cast_copy_exiles_creature_gains_life_unprepares(self) -> None:
        game, emeritus = self._prepared_game()
        p0, p1 = game.players
        target = p1.zones[Zone.BATTLEFIELD].get_all()[0]

        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p0._script.append(target)  # Swords target
        emeritus.cast_prepared_spell(game)
        # Resolve the spell on the stack via priority passes.
        from engine.stack import priority_loop

        p0._script.append("pass")
        p1._script.append("pass")
        priority_loop(game)

        assert target in p1.zones[Zone.EXILE].get_all()
        assert target not in p1.zones[Zone.BATTLEFIELD].get_all()
        assert p1.life == 22  # gained life equal to its power (2)
        assert emeritus.is_prepared is False
        # The copy ceased to exist: not in any graveyard or exile.
        assert all(
            c.name != "Swords to Plowshares"
            for p in game.players
            for z in (Zone.GRAVEYARD, Zone.EXILE)
            for c in p.zones[z].get_all()
        )
        # Cost was paid.
        assert p0.mana_pool.total() == 0

    def test_cast_requires_mana(self) -> None:
        game, emeritus = self._prepared_game()
        p0 = game.players[0]
        p0.mana_pool.empty()
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)
        assert emeritus.is_prepared is True

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p0 = game.players[0]
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        emeritus.register_triggers(game)
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)


class TestSwordsHelper:
    def test_swords_cannot_be_cast_on_empty_board(self) -> None:
        game = create_game()
        swords = SwordsToPlowshares()
        assert swords.can_cast(game) is False
