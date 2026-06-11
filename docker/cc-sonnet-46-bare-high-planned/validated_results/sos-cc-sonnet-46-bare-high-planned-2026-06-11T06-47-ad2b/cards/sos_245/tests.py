"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer().name == "Witherbloom, the Balancer"

    def test_keywords(self) -> None:
        w = WitherbloomTheBalancer()
        assert Keyword.FLYING in w.keywords
        assert Keyword.DEATHTOUCH in w.keywords

    def test_stats(self) -> None:
        w = WitherbloomTheBalancer()
        assert w.base_power == 5
        assert w.base_toughness == 5


class TestAffinityForCreatures:
    def test_cost_reduction_by_creature_count(self) -> None:
        game = create_game()
        w = WitherbloomTheBalancer()
        _put_on_battlefield(game, 0, w)
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        _put_on_battlefield(game, 0, c1)
        _put_on_battlefield(game, 0, c2)
        # 3 creatures total (Witherbloom + 2), reduction = 3
        assert w.cost_reduction(game) == 3

    def test_no_reduction_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        w.owner = p1
        w.controller = p1
        assert w.cost_reduction(game) == 0


class TestSpellCostReduction:
    def test_grants_affinity_to_instant(self) -> None:
        """E3: instant/sorcery you cast costs less when Witherbloom is on BF."""
        from engine.casting import get_cost_reduction
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        _put_on_battlefield(game, 0, w)
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        _put_on_battlefield(game, 0, c1)

        # 2 creatures (Witherbloom + c1): reduction = 2 for instants
        inst = Instant(name="Test", mana_cost=ManaCost.parse("{5}"))
        inst.controller = p1
        reduction = get_cost_reduction(game, inst, p1)
        assert reduction == 2

    def test_no_reduction_for_creature_spells(self) -> None:
        """E3: Witherbloom's spell_cost_reduction is only queried for instant/sorcery."""
        from engine.casting import get_cost_reduction
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        _put_on_battlefield(game, 0, w)
        creature_spell = Creature(name="Beefcake", base_power=3, base_toughness=3,
                                  mana_cost=ManaCost.parse("{3}"))
        creature_spell.controller = p1
        # E3 only calls spell_cost_reduction for INSTANT/SORCERY
        reduction = get_cost_reduction(game, creature_spell, p1)
        assert reduction == 0  # self.cost_reduction=0 too (it's the card's own hook)

    def test_does_not_reduce_opponents_spells(self) -> None:
        """spell_cost_reduction only applies to Witherbloom's controller's spells."""
        from engine.casting import get_cost_reduction
        game = create_game()
        p1, p2 = game.players
        w = WitherbloomTheBalancer()
        _put_on_battlefield(game, 0, w)
        inst = Instant(name="Test", mana_cost=ManaCost.parse("{5}"))
        inst.controller = p2
        reduction = get_cost_reduction(game, inst, p2)
        assert reduction == 0
