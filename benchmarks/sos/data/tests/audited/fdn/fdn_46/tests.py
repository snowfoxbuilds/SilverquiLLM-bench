"""Audited tests for FDN 46 — Lunar Insight."""

from __future__ import annotations

from card_impl import LunarInsight
from engine.card import Creature, Sorcery
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestLunarInsightBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = LunarInsight(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = LunarInsight(owner=None)
        assert card.name == "Lunar Insight"

    def test_mana_cost(self) -> None:
        card = LunarInsight(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")


class TestLunarInsightResolve:
    """Draw a card for each different mana value among nonland permanents."""

    def test_draws_for_distinct_mana_values(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LunarInsight(owner=p1, controller=p1)
        # Add creatures with different mana costs
        c1 = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"), base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Angel", mana_cost=ManaCost.parse("{3}{W}{W}"), base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        # Add library cards
        for i in range(5):
            lc = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(lc)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        # MV 2 and MV 5 = 2 distinct values
        assert hand_after - hand_before == 2

    def test_same_mana_value_counts_once(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LunarInsight(owner=p1, controller=p1)
        # Two creatures with same MV
        c1 = Creature(name="Bear1", mana_cost=ManaCost.parse("{1}{G}"), base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Bear2", mana_cost=ManaCost.parse("{1}{R}"), base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        for i in range(5):
            lc = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(lc)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        # Both MV 2 = 1 distinct value
        assert hand_after - hand_before == 1

    def test_no_nonland_permanents_draws_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LunarInsight(owner=p1, controller=p1)
        for i in range(5):
            lc = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(lc)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 0

    def test_tokens_with_no_mana_cost_have_mv_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LunarInsight(owner=p1, controller=p1)
        # Token with no mana cost (MV 0)
        token = Creature(name="Token", base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.mana_cost = None
        game.get_battlefield(p1).add(token)
        # Also add a creature with MV 2
        c1 = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"), base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        for i in range(5):
            lc = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(lc)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        # MV 0 and MV 2 = 2 distinct values
        assert hand_after - hand_before == 2
