"""Tests for SOS 245 — Witherbloom, the Balancer (Affinity + affinity grant)."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell, TestSetupError


class BigSpell(Instant):
    """Test-only instant costing {4} (generic only), no targets/effect."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Big Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _creature(name: str, owner: Any) -> Creature:
    c = Creature(name=name, owner=owner, controller=owner,
                 base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name_cost_pt(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert c.name == "Witherbloom, the Balancer"
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestSelfAffinity:
    def test_cost_reduction_counts_creatures(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        bf = [_creature("A", p1), _creature("B", p1), _creature("C", p1)]
        set_board_state(game, 0, battlefield=bf, hand=[wither])
        assert wither.cost_reduction(game) == 3

    def test_real_cast_with_affinity(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        bf = [_creature("A", p1), _creature("B", p1)]
        # {6}{B}{G} minus 2 creatures = {4}{B}{G}
        set_board_state(game, 0, battlefield=bf, hand=[wither],
                        mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1,
                              ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert wither in p1.zones[Zone.BATTLEFIELD].get_all()
        assert p1.mana_pool.total() == 0


class TestGrantedAffinity:
    def test_instant_you_cast_is_cheaper(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        bolt = BigSpell(owner=p1, controller=p1)
        # 2 creatures (Witherbloom + Goblin) → {4} reduced to {2}.
        set_board_state(game, 0, battlefield=[wither, _creature("Goblin", p1)],
                        hand=[bolt], mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Big Spell")
        assert bolt in p1.zones[Zone.GRAVEYARD].get_all()
        assert p1.mana_pool.total() == 0

    def test_creature_spell_not_affected(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        vanilla = _creature("Vanilla", p1)
        vanilla.mana_cost = ManaCost.parse("{4}")
        set_board_state(game, 0, battlefield=[wither], hand=[vanilla],
                        mana={ManaType.COLORLESS: 2})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Vanilla")

    def test_opponents_spell_not_affected(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither])
        opp_bolt = BigSpell(owner=p2, controller=p2)
        set_board_state(game, 1, hand=[opp_bolt], mana={ManaType.COLORLESS: 2})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Big Spell")
