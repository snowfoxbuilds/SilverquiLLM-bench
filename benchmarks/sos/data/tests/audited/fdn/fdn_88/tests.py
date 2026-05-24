"""Audited tests for FDN 88 — Goblin Negotiation."""

from __future__ import annotations

from card_impl import GoblinNegotiation
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestGoblinNegotiationBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = GoblinNegotiation(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = GoblinNegotiation(owner=None)
        assert card.name == "Goblin Negotiation"

    def test_mana_cost(self) -> None:
        card = GoblinNegotiation(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{R}{R}")


class TestGoblinNegotiationResolve:
    """Deal X damage; create tokens for excess damage."""

    def test_deals_x_damage_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinNegotiation(owner=p1, controller=p1)
        target = Creature(name="Big", base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.x_value = 3
        card.on_resolve(game)
        assert getattr(target, "damage_marked", 0) == 3

    def test_creates_tokens_for_excess_damage(self) -> None:
        """X=5 on a 2-toughness creature → 3 excess → 3 Goblin tokens."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GoblinNegotiation(owner=p1, controller=p1)
        target = Creature(name="Small", base_power=1, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.x_value = 5
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after - bf_before == 3

    def test_no_tokens_when_no_excess(self) -> None:
        """X=2 on a 3-toughness creature → 0 excess → no tokens."""
        game = create_game()
        p1 = game.players[0]
        card = GoblinNegotiation(owner=p1, controller=p1)
        target = Creature(name="Tough", base_power=1, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.x_value = 2
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        # Only the original target (still there unless killed by SBAs)
        assert bf_after - bf_before == 0

    def test_fizzles_when_target_is_none(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinNegotiation(owner=p1, controller=p1)
        card.chosen_targets = [None]
        card.x_value = 5
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after == bf_before

    def test_x_equals_zero_no_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinNegotiation(owner=p1, controller=p1)
        target = Creature(name="Target", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.x_value = 0
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after - bf_before == 0

    def test_tokens_are_goblins(self) -> None:
        """Created tokens should be Goblins."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GoblinNegotiation(owner=p1, controller=p1)
        target = Creature(name="Tiny", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.x_value = 3
        card.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        goblins = [c for c in bf if "Goblin" in getattr(c, "subtypes", set())]
        assert len(goblins) == 2  # 3 - 1 = 2 excess
