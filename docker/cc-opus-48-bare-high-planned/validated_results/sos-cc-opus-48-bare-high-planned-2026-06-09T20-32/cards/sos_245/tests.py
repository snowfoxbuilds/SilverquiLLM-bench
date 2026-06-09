"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _bears(n, owner=None):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_keywords_and_stats(self):
        c = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")


class TestOwnAffinity:
    def test_reduction_equals_creature_count(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=_bears(3))
        assert get_cost_reduction(game, wb, p0) == 3

    def test_zero_creatures(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[])
        assert get_cost_reduction(game, wb, p0) == 0


class TestGrantedAffinity:
    def test_instant_reduced_by_creature_count(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb] + _bears(2))  # 3 creatures
        inst = Instant(name="Bolt", mana_cost=ManaCost.parse("{5}{R}"))
        assert get_cost_reduction(game, inst, p0) == 3

    def test_sorcery_reduced(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb] + _bears(1))  # 2 creatures
        sorc = Sorcery(name="Quake", mana_cost=ManaCost.parse("{4}"))
        assert get_cost_reduction(game, sorc, p0) == 2

    def test_creature_spell_not_granted(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        dude = Creature(name="Dude", mana_cost=ManaCost.parse("{5}"),
                        base_power=1, base_toughness=1)
        # Affinity grant only applies to instants/sorceries.
        assert get_cost_reduction(game, dude, p0) == 0

    def test_cast_instant_with_reduced_mana(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb] + _bears(2))  # 3 creatures
        inst = Instant(name="Big Bolt", mana_cost=ManaCost.parse("{5}{R}"))
        # {5}{R} - 3 = {2}{R}; provide exactly that.
        set_board_state(game, 0, hand=[inst],
                        mana={ManaType.COLORLESS: 2, ManaType.RED: 1})
        cast_spell(game, 0, "Big Bolt")
        assert game.get_graveyard(p0).contains(inst)
