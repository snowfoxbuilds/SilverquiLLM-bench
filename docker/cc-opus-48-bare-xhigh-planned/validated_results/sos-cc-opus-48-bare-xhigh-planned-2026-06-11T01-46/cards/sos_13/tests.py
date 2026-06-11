"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _inklings(game, pidx):
    return [c for c in game.get_battlefield(game.players[pidx]).get_all()
            if "Inkling" in getattr(c, "subtypes", set())]


class TestProperties:
    def test_static(self):
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.name == "Emeritus of Truce // Swords to Plowshares"
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert c.base_power == 3 and c.base_toughness == 3
        assert {"Cat", "Cleric"} <= c.subtypes


class TestETB:
    def test_token_to_target_player_and_prepared(self):
        game = create_game()
        p0, p1 = game.players
        p0._script.append(p1)  # token goes to the opponent
        set_board_state(game, 1, battlefield=[
            Creature(name="Bear", base_power=2, base_toughness=2),
            Creature(name="Bear2", base_power=2, base_toughness=2),
        ])
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        inks = _inklings(game, 1)
        assert len(inks) == 1
        assert Keyword.FLYING in inks[0].keywords
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if isinstance(c, EmeritusOfTruceSwordsToPlowshares))
        # opponent now controls 3 creatures, you control 1 → prepared.
        assert emeritus._prepared is True

    def test_not_prepared_when_you_have_enough(self):
        game = create_game()
        p0, p1 = game.players
        p0._script.append(p0)  # token to yourself
        set_board_state(game, 1, battlefield=[
            Creature(name="Bear", base_power=2, base_toughness=2),
        ])
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert len(_inklings(game, 0)) == 1
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if isinstance(c, EmeritusOfTruceSwordsToPlowshares))
        # you control 2 (Emeritus + Inkling), opponent 1 → not prepared.
        assert emeritus._prepared is False


class TestSwordsToPlowshares:
    def test_exile_and_gain_life(self):
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Big", base_power=5, base_toughness=5)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[SwordsToPlowshares(owner=None)],
                        mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Swords to Plowshares", targets=[bear])
        assert game.get_exile(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)
        assert p1.life == 25  # controller of the creature gains its power (5)


class TestPreparedCast:
    def test_cast_prepared_spell_unprepares(self):
        game = create_game()
        p0, p1 = game.players
        p0._script.append(p1)  # ETB token to opponent → becomes prepared
        target_bear = Creature(name="Victim", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[
            target_bear,
            Creature(name="Bear2", base_power=2, base_toughness=2),
        ])
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if isinstance(c, EmeritusOfTruceSwordsToPlowshares))
        assert emeritus._prepared is True

        # Cast the prepared Swords copy at target_bear.
        p0._script.append(target_bear)
        ab = emeritus.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(source=emeritus, controller=p0,
                                        cost=ab.cost, effect=ab.effect,
                                        is_mana_ability=False)
        activate_ability(game, p0, inst)
        _resolve_stack(game)

        assert game.get_exile(p1).contains(target_bear)
        assert p1.life == 23  # gains target's power (3)
        assert emeritus._prepared is False

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus._prepared = False
        ab = emeritus.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(source=emeritus, controller=p0,
                                        cost=ab.cost, effect=ab.effect,
                                        is_mana_ability=False)
        with pytest.raises(Exception):
            activate_ability(game, p0, inst)
