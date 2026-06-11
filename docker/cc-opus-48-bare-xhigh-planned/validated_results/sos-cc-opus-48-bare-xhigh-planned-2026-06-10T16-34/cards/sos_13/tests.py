"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _bears(n, controller=None):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_bare_construct_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.prepared is False


class TestSwordsHelper:
    def test_exiles_and_grants_life(self):
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="VictimBear", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear], life=20)
        swords = SwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[swords], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Swords to Plowshares", targets=[bear])
        assert game.get_exile(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert p2.life == 24  # controller of exiled creature gains its power (4)


class TestEnterTheBattlefield:
    def test_creates_inkling_for_target_player(self):
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p1._script.append(p1)  # target player = self
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        inklings = [c for c in game.get_battlefield(p1).get_all()
                    if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1
        tok = inklings[0]
        assert tok.base_power == 1 and tok.base_toughness == 1
        assert Keyword.FLYING in tok.keywords

    def test_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(3))  # opponent has 3 creatures
        card = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p1._script.append(p1)  # token to self → you=2 (token+Emeritus), opp=3
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert card.prepared is True

    def test_not_prepared_when_not_outnumbered(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(1))  # opponent has 1
        card = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p1._script.append(p1)  # you=2 (token+Emeritus), opp=1
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert card.prepared is False


class TestPreparedCast:
    def test_cast_prepared_exiles_and_unprepares(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        bear = Creature(name="EnemyBear", base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[bear], life=20)
        emeritus.prepared = True
        p1._script.append(bear)  # Swords target
        result = emeritus.cast_prepared_spell(game)
        _resolve_all(game)
        assert result is True
        assert emeritus.prepared is False
        assert game.get_exile(p2).contains(bear)
        assert p2.life == 23  # bear's controller gains its power (3)

    def test_no_legal_target_stays_prepared(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # No creatures anywhere on the battlefield.
        emeritus.prepared = True
        p1._script.append(None)  # no legal target
        result = emeritus.cast_prepared_spell(game)
        assert result is False
        assert emeritus.prepared is True
        assert len(game.get_exile(p1).get_all()) == 0  # no lingering Swords copy
