"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state, cast_spell


class DamageInstant(Instant):
    """Test instant {3}{R}: deals 1 damage to the non-active player."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Damage Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 1)


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_static(self):
        c = WitherbloomTheBalancer(owner=None)
        assert c.name == "Witherbloom, the Balancer"
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes


class TestSelfAffinity:
    def test_three_creatures_reduce_own_cost(self):
        game = create_game()
        set_board_state(game, 0, battlefield=_bears(3))
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        # 6 generic - 3 creatures = 3 generic; {3}{B}{G} payable with 3C+B+G
        cast_spell(game, 0, "Witherbloom, the Balancer")
        bf = game.get_battlefield(game.players[0])
        assert any(getattr(c, "name", "") == "Witherbloom, the Balancer" for c in bf.get_all())

    def test_no_reduction_with_no_creatures(self):
        game = create_game()
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_grants_affinity_to_instants(self):
        game = create_game()
        p0, p1 = game.players
        wb = WitherbloomTheBalancer(owner=None)
        # Witherbloom + 2 bears = 3 creatures → instant {3}{R} costs just {R}
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        set_board_state(game, 0, hand=[DamageInstant(owner=None)],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Damage Instant")
        assert p1.life == 19  # resolved despite only {R} available

    def test_grant_requires_witherbloom(self):
        game = create_game()
        # Three bears but NO Witherbloom → no granted affinity
        set_board_state(game, 0, battlefield=_bears(3))
        set_board_state(game, 0, hand=[DamageInstant(owner=None)],
                        mana={ManaType.RED: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Damage Instant")

    def test_grant_scales_partial(self):
        game = create_game()
        p0, p1 = game.players
        wb = WitherbloomTheBalancer(owner=None)
        # Witherbloom alone = 1 creature → {3}{R} becomes {2}{R}
        set_board_state(game, 0, battlefield=[wb])
        set_board_state(game, 0, hand=[DamageInstant(owner=None)],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Damage Instant")
        assert p1.life == 19
