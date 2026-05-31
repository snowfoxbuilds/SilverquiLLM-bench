"""Tests for sos_245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_base_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_base_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestWitherbloomCostReduction:
    """Affinity for creatures: costs {1} less for each creature you control."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # No creatures on battlefield besides possibly Witherbloom itself
        # (not yet placed). With an empty battlefield:
        set_board_state(game, 0, battlefield=[])
        assert card.cost_reduction(game) == 0

    def test_three_creatures_reduces_by_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear{i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_five_creatures_reduces_by_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear{i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 5

    def test_includes_witherbloom_itself_if_on_battlefield(self) -> None:
        """When Witherbloom is on the battlefield, it counts itself."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        two_others = [
            Creature(name=f"Bear{i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(2)
        ]
        set_board_state(game, 0, battlefield=[card] + two_others)
        # 3 creatures total on battlefield
        assert card.cost_reduction(game) == 3


class TestWitherbloomAffinityGranting:
    """Witherbloom grants affinity for creatures to instants/sorceries."""

    def test_grants_affinity_flag_is_set(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.grants_affinity_for_creatures is True

    def test_affinity_flag_readable_from_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf = game.get_battlefield(p1)
        for obj in bf.get_all():
            if obj is card:
                assert getattr(obj, "grants_affinity_for_creatures", False) is True
