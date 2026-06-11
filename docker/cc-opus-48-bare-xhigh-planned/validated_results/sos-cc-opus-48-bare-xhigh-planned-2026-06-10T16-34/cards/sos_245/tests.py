"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_static(self):
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestOwnAffinity:
    def test_no_creatures_no_reduction(self):
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_three_creatures_reduce_by_three(self):
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=_bears(3))
        # generic 6 → reduction 3
        assert card.cost_reduction(game) == 3
        assert get_cost_reduction(game, card, p1) == 3

    def test_real_cast_with_reduction(self):
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=None)
        # 2 other creatures → {6}{B}{G} costs {4}{B}{G} → 6 mana
        set_board_state(game, 0, battlefield=_bears(2), hand=[card],
                        mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1, ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(card)
        assert p1.mana_pool.total() == 0


class TestGrantedAffinity:
    def test_instant_reduced_by_creature_count(self):
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        # battlefield: Witherbloom + 2 bears = 3 creatures
        set_board_state(game, 0, battlefield=[wither] + _bears(2))
        inst = Instant(name="BigZap", mana_cost=ManaCost.parse("{5}{R}"))
        inst.controller = p1
        assert get_cost_reduction(game, inst, p1) == 3

    def test_grant_only_applies_to_instant_sorcery(self):
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither] + _bears(2))
        # A creature spell is NOT reduced by the granted affinity.
        creature_spell = Creature(name="Ogre", mana_cost=ManaCost.parse("{5}{R}"),
                                  base_power=4, base_toughness=4)
        creature_spell.controller = p1
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_grant_real_cast(self):
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither] + _bears(2))  # 3 creatures
        inst = Instant(name="BigZap", mana_cost=ManaCost.parse("{5}{R}"))
        # reduced by 3 → {2}{R} = 3 mana
        set_board_state(game, 0, battlefield=[wither] + _bears(2), hand=[inst],
                        mana={ManaType.COLORLESS: 2, ManaType.RED: 1})
        cast_spell(game, 0, "BigZap")
        assert game.get_graveyard(p1).contains(inst)
        assert p1.mana_pool.total() == 0

    def test_zero_creatures_no_grant(self):
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        # only Witherbloom is a creature → count 1; remove it to test 0
        inst = Instant(name="Z", mana_cost=ManaCost.parse("{3}{R}"))
        inst.controller = p1
        # No Witherbloom on battlefield at all → no grant source
        assert get_cost_reduction(game, inst, p1) == 0
