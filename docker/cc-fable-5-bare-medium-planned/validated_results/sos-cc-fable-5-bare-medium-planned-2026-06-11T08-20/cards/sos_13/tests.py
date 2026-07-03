"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.types import Keyword, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell

NAME = "Emeritus of Truce // Swords to Plowshares"


def _cast_emeritus(game, target_player, opp_creatures=0):
    p0 = game.players[0]
    bears = [Creature(name=f"OppBear{i}", base_power=2, base_toughness=2)
             for i in range(opp_creatures)]
    if bears:
        set_board_state(game, 1, battlefield=bears)
    set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares()],
                    mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
    p0._script.append(target_player)  # token recipient
    cast_spell(game, 0, NAME)


class TestEmeritusOfTruce:
    def test_etb_creates_token_for_target_player(self):
        game = create_game()
        p1 = game.players[1]
        _cast_emeritus(game, p1)
        inklings = [c for c in game.get_battlefield(p1).get_all()
                    if c.name == "Inkling"]
        assert len(inklings) == 1
        tok = inklings[0]
        assert tok.power == 1 and tok.toughness == 1
        assert Keyword.FLYING in tok.keywords
        assert tok.is_token

    def test_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p0, p1 = game.players
        # Opponent has 2 bears + receives the token = 3 vs our 1 (Emeritus)
        _cast_emeritus(game, p1, opp_creatures=2)
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if c.name == NAME)
        assert emeritus.is_prepared
        swords = [c for c in game.get_exile(p0).get_all()
                  if c.name == "Swords to Plowshares"]
        assert len(swords) == 1

    def test_not_prepared_when_token_given_to_self(self):
        game = create_game()
        p0 = game.players[0]
        # Token to ourselves: we have Emeritus + Inkling = 2, opponent 0.
        _cast_emeritus(game, p0)
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if c.name == NAME)
        assert not emeritus.is_prepared
        assert not any(c.name == "Swords to Plowshares"
                       for c in game.get_exile(p0).get_all())

    def test_cast_prepared_spell_exiles_and_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        _cast_emeritus(game, p1, opp_creatures=2)
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if c.name == NAME)
        assert emeritus.is_prepared
        # Pay {W} and cast the copy targeting an opponent bear.
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        bear = next(c for c in game.get_battlefield(p1).get_all()
                    if c.name == "OppBear0")
        p0._script.append(bear)  # target for Swords
        assert emeritus.cast_prepared_spell(game)
        # Resolve the stack.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert game.get_exile(p1).contains(bear)
        assert p1.life == 22  # bear's power 2 gained by its controller
        assert not emeritus.is_prepared
        assert not any(c.name == "Swords to Plowshares"
                       for c in game.get_exile(p0).get_all())

    def test_cannot_cast_prepared_without_mana(self):
        game = create_game()
        p0, p1 = game.players
        _cast_emeritus(game, p1, opp_creatures=2)
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if c.name == NAME)
        set_board_state(game, 0, mana={})  # no {W}
        assert not emeritus.cast_prepared_spell(game)
        assert emeritus.is_prepared  # still prepared


class TestSwordsToPlowshares:
    def test_standalone_swords(self):
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Bear", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[SwordsToPlowshares()],
                        mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Swords to Plowshares", targets=[bear])
        assert game.get_exile(p1).contains(bear)
        assert p1.life == 24
