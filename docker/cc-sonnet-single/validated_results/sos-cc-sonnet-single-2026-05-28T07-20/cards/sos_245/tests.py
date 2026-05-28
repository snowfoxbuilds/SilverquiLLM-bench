"""Tests for SOS 245 — Witherbloom, the Balancer.

Requirements under test:
1. Static properties: Legendary Creature — Elder Dragon, 5/5, {6}{B}{G},
   Flying and Deathtouch keywords, Legendary supertype, Elder Dragon subtypes.
2. Own affinity for creatures: cost_reduction(game) returns the number of
   creatures the controller controls (0 when no creatures, N when N creatures).
3. Affinity is based solely on the controller's battlefield, not the opponent's.
4. When controller is None, cost_reduction() returns 0 without crashing.
5. Grants affinity to instants and sorceries via get_affinity_cost_reduction(spell, game)
   (or an analogous method): returns the creature count for controller's spells.
6. The granted affinity does NOT apply to non-instant/sorcery spell types.
7. The granted affinity does NOT apply to opponent's spells.
8. Uncontrolled Witherbloom returns 0 (no crash) for the grants method.
"""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestWitherbloomStaticProperties:
    """Static characteristics must match the SOS 245 card spec."""

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_mana_cost_contains_black_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert ManaType.BLACK in card.mana_cost.pips

    def test_mana_cost_contains_green_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert ManaType.GREEN in card.mana_cost.pips

    def test_base_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_base_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_is_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Own affinity for creatures — cost_reduction()
# ---------------------------------------------------------------------------


class TestWitherbloomOwnAffinityForCreatures:
    """cost_reduction(game) counts creatures the controller controls."""

    def test_zero_when_controller_has_no_creatures(self) -> None:
        """With no creatures on the battlefield, cost_reduction() returns 0."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_gives_reduction_of_one(self) -> None:
        """One creature on the battlefield reduces cost by 1."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Grizzly Bears",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[bear])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_three_creatures_give_reduction_of_three(self) -> None:
        """Three creatures reduce cost by 3."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            Creature(
                name=f"Bear {i}",
                base_power=2,
                base_toughness=2,
                owner=p1,
                controller=p1,
            )
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_witherbloom_itself_on_battlefield_counts_as_creature(self) -> None:
        """Witherbloom itself is a creature and must count toward cost_reduction."""
        game = create_game()
        p1 = game.players[0]
        # Place Witherbloom on the battlefield and create a separate instance
        # to measure the reduction.
        on_board = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[on_board])
        # The card being cast uses its own controller to count creatures.
        casting_copy = WitherbloomTheBalancer(owner=p1, controller=p1)
        # The creature on the battlefield (on_board) counts — reduction >= 1.
        assert casting_copy.cost_reduction(game) >= 1

    def test_opponent_creatures_not_counted(self) -> None:
        """Creatures the opponent controls do not reduce Witherbloom's cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        opponent_bear = Creature(
            name="Opponent Bear",
            base_power=2,
            base_toughness=2,
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, battlefield=[opponent_bear])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_no_controller_returns_zero(self) -> None:
        """When controller is None, cost_reduction must return 0 without crashing."""
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        card.controller = None
        result = card.cost_reduction(game)
        assert result == 0

    def test_cost_reduction_does_not_count_non_creature_permanents(self) -> None:
        """Non-creature permanents on the battlefield are not counted."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import Enchantment
        enchantment = Enchantment(
            name="Pacifism",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[enchantment])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_large_creature_count_returns_correct_value(self) -> None:
        """With 6 creatures, cost_reduction returns 6."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            Creature(
                name=f"Soldier {i}",
                base_power=1,
                base_toughness=1,
                owner=p1,
                controller=p1,
            )
            for i in range(6)
        ]
        set_board_state(game, 0, battlefield=creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 6


# ---------------------------------------------------------------------------
# Granted affinity — instants and sorceries you cast get affinity for creatures
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinityToSpells:
    """Witherbloom must expose get_affinity_cost_reduction(spell, game) that
    returns the number of creatures the controller controls for eligible spells."""

    def test_has_grants_method(self) -> None:
        """Witherbloom must expose a method for granting affinity to spells."""
        card = WitherbloomTheBalancer(owner=None)
        assert hasattr(card, "get_affinity_cost_reduction"), (
            "WitherbloomTheBalancer must implement get_affinity_cost_reduction(spell, game)"
        )

    def test_grants_method_is_callable(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert callable(card.get_affinity_cost_reduction)

    def test_instant_gets_affinity_reduction_equal_to_creature_count(self) -> None:
        """An instant cast by controller gets cost_reduction equal to creature count."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(
            name="Bear",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom, bear])

        reduction = witherbloom.get_affinity_cost_reduction(instant, game)
        # Two creatures on the battlefield (witherbloom + bear) → reduction is 2.
        assert reduction == 2

    def test_sorcery_gets_affinity_reduction_equal_to_creature_count(self) -> None:
        """A sorcery cast by controller gets cost_reduction equal to creature count."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])

        reduction = witherbloom.get_affinity_cost_reduction(sorcery, game)
        # One creature (witherbloom) on the battlefield → reduction is 1.
        assert reduction == 1

    def test_instant_gets_zero_reduction_when_no_creatures(self) -> None:
        """When controller controls no creatures, an instant gets 0 reduction."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant = Instant(name="Shock", owner=p1, controller=p1)
        # Witherbloom is NOT on the battlefield here.

        reduction = witherbloom.get_affinity_cost_reduction(instant, game)
        assert reduction == 0

    def test_creature_card_does_not_get_granted_affinity(self) -> None:
        """A creature card does not get affinity for creatures from Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(
            name="Bear",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[witherbloom])

        result = witherbloom.get_affinity_cost_reduction(bear, game)
        assert not result, (
            "Creature cards must not receive granted affinity from Witherbloom"
        )

    def test_opponent_instant_does_not_get_granted_affinity(self) -> None:
        """Instants cast by the opponent are not affected by Witherbloom's grant."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_instant = Instant(
            name="Counterspell", owner=p2, controller=p2
        )
        set_board_state(game, 0, battlefield=[witherbloom])

        result = witherbloom.get_affinity_cost_reduction(opponent_instant, game)
        assert not result, (
            "Opponent's instants must not receive affinity from Witherbloom"
        )

    def test_uncontrolled_witherbloom_returns_zero_for_grants(self) -> None:
        """When Witherbloom has no controller, the grants method returns 0 safely."""
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        card.controller = None
        instant = Instant(name="Test Instant", owner=None)
        result = card.get_affinity_cost_reduction(instant, game)
        assert result == 0

    def test_granted_affinity_counts_only_controller_creatures(self) -> None:
        """The reduction for instants only counts the caster's creatures, not opponents'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant = Instant(name="Bolt", owner=p1, controller=p1)
        opponent_bear = Creature(
            name="Opponent Bear",
            base_power=2,
            base_toughness=2,
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 0, battlefield=[witherbloom])
        set_board_state(game, 1, battlefield=[opponent_bear])

        reduction = witherbloom.get_affinity_cost_reduction(instant, game)
        # Only witherbloom (p1's creature) counts → reduction = 1.
        assert reduction == 1
