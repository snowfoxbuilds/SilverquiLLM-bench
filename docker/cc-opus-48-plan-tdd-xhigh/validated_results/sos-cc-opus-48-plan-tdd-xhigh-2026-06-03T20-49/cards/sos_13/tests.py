"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, _resolve_top_of_stack


def _creature(name="Bear", power=2):
    return Creature(name=name, base_power=power, base_toughness=2)


def _cast_emeritus(game, token_target=None):
    em = EmeritusOfTruceSwordsToPlowshares(owner=None)
    set_board_state(game, 0, hand=[em], mana={ManaType.WHITE: 3})
    if token_target is not None:
        em._token_target = token_target
    cast_spell(game, 0, "Emeritus of Truce")
    return em


def _inklings(game, player):
    return [
        o for o in player.zones[Zone.BATTLEFIELD].get_all()
        if getattr(o, "name", None) == "Inkling"
    ]


def _activate_stp(game, player, em):
    ability = em.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=em,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    _resolve_top_of_stack(game)


class TestProperties:
    def test_is_creature(self):
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self):
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).name
            == "Emeritus of Truce"
        )

    def test_mana_cost(self):
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).mana_cost
            == ManaCost.parse("{1}{W}{W}")
        )

    def test_power_toughness(self):
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.base_power == 3 and c.base_toughness == 3

    def test_not_prepared_initially(self):
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).prepared is False


class TestEnterToken:
    def test_creates_inkling_for_controller(self):
        game = create_game()
        p0 = game.players[0]
        _cast_emeritus(game)
        assert len(_inklings(game, p0)) == 1

    def test_inkling_is_one_one_flyer(self):
        game = create_game()
        p0 = game.players[0]
        _cast_emeritus(game)
        ink = _inklings(game, p0)[0]
        assert ink.base_power == 1 and ink.base_toughness == 1
        assert Keyword.FLYING in ink.keywords

    def test_token_target_can_be_opponent(self):
        game = create_game()
        p0, p1 = game.players
        _cast_emeritus(game, token_target=p1)
        assert len(_inklings(game, p1)) == 1
        assert len(_inklings(game, p0)) == 0


class TestPrepared:
    def test_becomes_prepared_when_outnumbered(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=[_creature(f"Bear{i}") for i in range(3)])
        em = _cast_emeritus(game)
        assert em.prepared is True

    def test_not_prepared_when_not_outnumbered(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=[_creature("Lonely")])
        em = _cast_emeritus(game)
        assert em.prepared is False


class TestSwordsToPlowshares:
    def test_exiles_and_grants_life(self):
        game = create_game()
        p0, p1 = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        victim = _creature("Ogre", power=4)
        set_board_state(game, 0, battlefield=[em], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        em.prepared = True
        em._resolve_target = victim
        _activate_stp(game, p0, em)
        assert victim in p1.zones[Zone.EXILE].get_all()
        assert p1.life == 24
        assert em.prepared is False

    def test_requires_prepared(self):
        game = create_game()
        p0, p1 = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        victim = _creature("Ogre", power=4)
        set_board_state(game, 0, battlefield=[em], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim])
        em.prepared = False
        em._resolve_target = victim
        ability = em.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(
            source=em, controller=p0,
            cost=ability.cost, effect=ability.effect, is_mana_ability=False,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, p0, inst)
        assert victim not in p1.zones[Zone.EXILE].get_all()

    def test_cannot_activate_twice(self):
        game = create_game()
        p0, p1 = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        v1 = _creature("V1", power=1)
        v2 = _creature("V2", power=1)
        set_board_state(game, 0, battlefield=[em], mana={ManaType.WHITE: 2})
        set_board_state(game, 1, battlefield=[v1, v2])
        em.prepared = True
        em._resolve_target = v1
        _activate_stp(game, p0, em)
        em._resolve_target = v2
        ability = em.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(
            source=em, controller=p0,
            cost=ability.cost, effect=ability.effect, is_mana_ability=False,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, p0, inst)
        assert v2 not in p1.zones[Zone.EXILE].get_all()
