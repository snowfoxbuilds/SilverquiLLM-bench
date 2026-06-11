"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.casting import cast_spell_free
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"
MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _bear(name="Bear", power=2, toughness=2):
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _find_inkling(player):
    return [
        c for c in player.zones[Zone.BATTLEFIELD].get_all()
        if getattr(c, "name", None) == "Inkling"
    ]


def _exiled_swords(player):
    return [
        c for c in player.zones[Zone.EXILE].get_all()
        if getattr(c, "name", None) == "Swords to Plowshares"
    ]


class TestStatics:
    def test_constructs_bare_with_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == FULL_NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert card.subtypes == {"Cat", "Cleric"}


class TestEnterTheBattlefield:
    def test_target_player_creates_inkling_token(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares()],
                        mana=MANA)

        cast_spell(game, 0, FULL_NAME, targets=[p2])

        inklings = _find_inkling(p2)
        assert len(inklings) == 1
        token = inklings[0]
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.is_token

    def test_becomes_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus], mana=MANA)
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])

        cast_spell(game, 0, FULL_NAME, targets=[p2])

        # p2: 2 bears + Inkling = 3 creatures > p1's 1 -> prepared.
        assert emeritus.is_prepared
        assert len(_exiled_swords(p1)) == 1

    def test_not_prepared_when_opponent_does_not_have_more(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus], mana=MANA)
        set_board_state(game, 1, battlefield=[_bear("B1")])

        # Token to p1: both players end with 2 creatures.
        cast_spell(game, 0, FULL_NAME, targets=[p1])

        assert not emeritus.is_prepared
        assert len(_exiled_swords(p1)) == 0


class TestPreparedSpell:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        big = _bear("Big", power=4, toughness=4)
        set_board_state(game, 0, hand=[emeritus], mana=MANA)
        set_board_state(game, 1, battlefield=[big, _bear("Small")])
        cast_spell(game, 0, FULL_NAME, targets=[p2])
        assert emeritus.is_prepared
        return game, emeritus, big

    def test_casting_copy_exiles_creature_and_unprepares(self):
        game, emeritus, big = self._prepared_setup()
        p1, p2 = game.players
        copy = _exiled_swords(p1)[0]

        p1._script.append(big)  # target for Swords to Plowshares
        cast_spell_free(game, p1, copy, Zone.EXILE)
        p1._script.extend(["pass", "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        # Big was exiled; its controller gained life equal to its power.
        assert p2.zones[Zone.EXILE].contains(big)
        assert not p2.zones[Zone.BATTLEFIELD].contains(big)
        assert p2.life == 24
        # Casting the copy unprepared the Emeritus.
        assert not emeritus.is_prepared
        # The resolved copy ceased to exist — no Swords anywhere.
        for player in game.players:
            for zone in Zone:
                assert all(
                    getattr(c, "name", None) != "Swords to Plowshares"
                    for c in player.zones[zone].get_all()
                )

    def test_copy_vanishes_if_emeritus_leaves_while_prepared(self):
        game, emeritus, big = self._prepared_setup()
        p1, p2 = game.players
        assert len(_exiled_swords(p1)) == 1

        from engine.game import destroy
        destroy(game, emeritus)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(emeritus)
        assert not emeritus.is_prepared
        assert len(_exiled_swords(p1)) == 0
