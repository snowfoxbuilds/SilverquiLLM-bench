"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.casting import CastingError
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_emeritus(game, target_player):
    emeritus = EmeritusOfTruceSwordsToPlowshares()
    game.players[0].zones[Zone.HAND].add(emeritus)
    emeritus.owner = emeritus.controller = game.players[0]
    game.players[0].mana_pool.add(ManaType.COLORLESS, 1)
    game.players[0].mana_pool.add(ManaType.WHITE, 2)
    cast_spell(
        game, 0, "Emeritus of Truce // Swords to Plowshares",
        targets=[target_player],
    )
    return emeritus


class TestProperties:
    def test_constructs_bare_with_full_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3 and card.base_toughness == 3
        assert card.is_prepared is False


class TestEnterTheBattlefield:
    def test_target_player_creates_inkling(self) -> None:
        """Opponent (targeted) gets the 1/1 flying Inkling token."""
        game = create_game()
        p1, p2 = game.players
        _cast_emeritus(game, p2)

        inklings = [
            c for c in p2.zones[Zone.BATTLEFIELD].get_all()
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.is_token
        assert Keyword.FLYING in token.keywords
        assert token.power == 1 and token.toughness == 1

    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        """Opponent has 2 bears + new Inkling (3) vs your 1 → prepared."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("A"), _bear("B")])

        emeritus = _cast_emeritus(game, p2)

        assert emeritus.is_prepared
        # Rule 722.3c: a Swords to Plowshares copy waits in exile.
        copies = [
            c for c in p1.zones[Zone.EXILE].get_all()
            if isinstance(c, SwordsToPlowshares)
        ]
        assert len(copies) == 1

    def test_not_prepared_when_creature_counts_equal(self) -> None:
        """Token to self: you have Emeritus+Inkling (2), opponent 2 → not prepared."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("A"), _bear("B")])

        emeritus = _cast_emeritus(game, p1)

        assert not emeritus.is_prepared
        assert len(p1.zones[Zone.EXILE]) == 0


class TestPreparedCasting:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("A"), _bear("B")])
        emeritus = _cast_emeritus(game, p2)
        assert emeritus.is_prepared
        return game, emeritus

    def test_cast_copy_exiles_creature_gains_life_unprepares(self) -> None:
        game, emeritus = self._prepared_setup()
        p1, p2 = game.players
        bear = next(
            c for c in p2.zones[Zone.BATTLEFIELD].get_all()
            if c.name == "A"
        )
        p1.mana_pool.add(ManaType.WHITE, 1)
        p2_life = p2.life
        p1._script.append(bear)  # target for the Swords copy

        emeritus.cast_prepared_spell(game)
        from test_utils import _resolve_top_of_stack

        _resolve_top_of_stack(game)

        assert p2.zones[Zone.EXILE].contains(bear)
        assert p2.life == p2_life + 2  # bear's power
        assert not emeritus.is_prepared
        assert p1.mana_pool.total() == 0  # the {W} was paid

    def test_cannot_cast_without_mana(self) -> None:
        game, emeritus = self._prepared_setup()
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)
        assert emeritus.is_prepared  # still prepared

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emeritus = _cast_emeritus(game, p1)  # token to self → not prepared
        p1.mana_pool.add(ManaType.WHITE, 1)
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)
