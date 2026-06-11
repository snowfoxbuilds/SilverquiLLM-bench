"""Tests for Witherbloom, the Balancer (sos_245)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Zone, CardType, Keyword
from engine.casting import get_cost_reduction


class TestWitherbloomTheBalancer:
    def test_keywords(self):
        """Has Flying and Deathtouch."""
        wb = WitherbloomTheBalancer()
        assert Keyword.FLYING in wb.keywords
        assert Keyword.DEATHTOUCH in wb.keywords

    def test_self_affinity_no_creatures(self):
        """0 creatures → no cost reduction for self."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer()
        wb.owner = p1
        wb.controller = p1
        red = get_cost_reduction(game, wb, p1)
        assert red == 0

    def test_self_affinity_with_creatures(self):
        """Costs {1} less per creature you control."""
        game = create_game()
        p1 = game.players[0]
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[bear1, bear2])
        wb = WitherbloomTheBalancer()
        wb.owner = p1
        wb.controller = p1
        red = get_cost_reduction(game, wb, p1)
        assert red == 2

    def test_granted_affinity_to_instant(self):
        """Instant/sorcery spells also get affinity for creatures (E3)."""
        game = create_game()
        p1 = game.players[0]
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        wb = WitherbloomTheBalancer()
        wb.owner = p1
        wb.controller = p1
        set_board_state(game, 0, battlefield=[bear1, wb])
        wb.controller = p1  # re-set after set_board_state

        class TestInstant(Instant):
            def __init__(self):
                super().__init__(name="TestInstant", mana_cost=ManaCost.parse("{5}"))

        spell = TestInstant()
        spell.owner = p1
        spell.controller = p1
        # 2 creatures on battlefield (bear1 + wb): spell costs 2 less
        red = get_cost_reduction(game, spell, p1)
        assert red == 2

    def test_granted_affinity_not_for_opponent(self):
        """Grant only applies to controller's spells, not opponent's."""
        game = create_game()
        p1, p2 = game.players
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        wb = WitherbloomTheBalancer()
        wb.owner = p1
        wb.controller = p1
        set_board_state(game, 0, battlefield=[bear1, wb])
        wb.controller = p1

        class TestInstant(Instant):
            def __init__(self):
                super().__init__(name="TestInstant", mana_cost=ManaCost.parse("{5}"))

        spell = TestInstant()
        spell.owner = p2
        spell.controller = p2
        # Opponent's spell: no reduction from Witherbloom
        red = get_cost_reduction(game, spell, p2)
        assert red == 0

    def test_affinity_clamped_at_generic(self):
        """Cost reduction never exceeds the generic portion of the mana cost."""
        game = create_game()
        p1 = game.players[0]
        # 10 creatures but spell only has {3} generic → max reduction = 3
        for i in range(10):
            c = Creature(name=f"Bear{i}", base_power=1, base_toughness=1)
            c.owner = p1
            c.controller = p1
            p1.zones[Zone.BATTLEFIELD].add(c)

        class SmallInstant(Instant):
            def __init__(self):
                super().__init__(name="Small", mana_cost=ManaCost.parse("{3}{U}"))

        wb = WitherbloomTheBalancer()
        wb.owner = p1
        wb.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(wb)
        wb.controller = p1

        spell = SmallInstant()
        spell.owner = p1
        spell.controller = p1
        red = get_cost_reduction(game, spell, p1)
        assert red == 3  # capped at {3} generic cost
