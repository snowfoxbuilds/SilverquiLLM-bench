"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _activate_prepared(game, player, emeritus, swords_target):
    aa = emeritus.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=emeritus, controller=player, cost=aa.cost,
        effect=aa.effect, is_mana_ability=False,
    )
    player._script.append(swords_target)
    activate_ability(game, player, inst)
    _drain(game)


class TestProperties:
    def test_full_dfc_name(self):
        c = EmeritusOfTruceSwordsToPlowshares()
        assert c.name == "Emeritus of Truce // Swords to Plowshares"
        assert c.base_power == 3 and c.base_toughness == 3
        assert {"Cat", "Cleric"} <= c.subtypes
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")


class TestEtbToken:
    def test_creates_inkling_for_target_player(self):
        game = create_game()
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0 = game.players[0]
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p0])
        inklings = [c for c in game.get_battlefield(p0).get_all()
                    if c.name == "Inkling"]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords
        assert inklings[0].base_power == 1 and inklings[0].base_toughness == 1


class TestPrepared:
    def test_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 1, battlefield=_bears(3))
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0 = game.players[0]
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p0])
        assert emeritus._prepared is True
        # The prepared special action is now available.
        assert len(emeritus.get_activated_abilities()) == 1

    def test_not_prepared_when_you_have_more(self):
        game = create_game()
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 1, battlefield=_bears(1))
        set_board_state(game, 0, battlefield=_bears(2), hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0 = game.players[0]
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p0])
        assert emeritus._prepared is False
        assert emeritus.get_activated_abilities() == []


class TestPreparedCast:
    def test_prepared_cast_exiles_and_gains_life(self):
        game = create_game()
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        emeritus._prepared = True
        victim = Creature(name="Victim", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[victim], life=20)
        p0, p1 = game.players
        _activate_prepared(game, p0, emeritus, victim)
        # Victim exiled; its controller (p1) gained life equal to its power (4).
        assert game.get_exile(p1).contains(victim)
        assert not game.get_battlefield(p1).contains(victim)
        assert p1.life == 24
        # Casting the prepared spell unprepares Emeritus.
        assert emeritus._prepared is False
        assert emeritus.get_activated_abilities() == []


class TestSwordsStandalone:
    def test_swords_exiles_and_gains_life(self):
        game = create_game()
        swords = SwordsToPlowshares(owner=None)
        target = Creature(name="Big", base_power=5, base_toughness=5)
        set_board_state(game, 0, hand=[swords], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[target], life=20)
        p1 = game.players[1]
        cast_spell(game, 0, "Swords to Plowshares", targets=[target])
        assert game.get_exile(p1).contains(target)
        assert p1.life == 25
