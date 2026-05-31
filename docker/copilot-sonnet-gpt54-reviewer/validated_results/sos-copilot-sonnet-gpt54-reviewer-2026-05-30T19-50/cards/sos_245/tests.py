"""Tests for Witherbloom, the Balancer (sos_245).

Covers:
- Static card attributes (name, mana cost, 5/5, Flying, Deathtouch, Legendary, Elder Dragon)
- Own affinity for creatures: cost_reduction() returns creature count
- Own affinity reduces effective cast cost
- Own affinity max reduction (min cost 0) with many creatures
- Static grant: instant/sorcery spells cast by controller get affinity for creatures
- Granted affinity does NOT apply to opponent's spells
- Granted affinity does NOT apply to non-instant/sorcery spells (e.g. another creature)
- Granted affinity stacks correctly with creature count
"""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell, get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestWitherbloomProperties:
    """Static card data must match the sos_245 spec."""

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

    def test_has_legendary_supertype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.keywords & Keyword.FLYING

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.keywords & Keyword.DEATHTOUCH


# ---------------------------------------------------------------------------
# Own affinity for creatures
# ---------------------------------------------------------------------------

class TestWitherbloomOwnAffinity:
    """cost_reduction() returns 1 per creature the controller controls."""

    def test_no_reduction_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_gives_three_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Creature{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_does_not_count_opponent_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_creature = Creature(name="OppBear", base_power=2, base_toughness=2,
                                owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[opp_creature])
        assert card.cost_reduction(game) == 0

    def test_no_controller_returns_zero(self) -> None:
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        card.controller = None
        assert card.cost_reduction(game) == 0

    def test_affinity_reduces_effective_cast_cost(self) -> None:
        """Casting Witherbloom itself costs 1 less per creature controlled."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # Base generic is 6, 3 creatures → reduction = 3
        reduction = get_cost_reduction(game, witherbloom, p1)
        assert reduction == 3

    def test_affinity_min_cost_is_zero(self) -> None:
        """With 10 creatures, reduction is capped so generic doesn't go below 0."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # Generic is 6, 10 creatures would reduce by 10 but capped at 6
        reduction = get_cost_reduction(game, witherbloom, p1)
        assert reduction == 6


# ---------------------------------------------------------------------------
# Static grant: instants/sorceries get affinity for creatures
# ---------------------------------------------------------------------------

class TestWitherbloomGrantsAffinity:
    """While Witherbloom is on battlefield, controller's instants/sorceries get affinity."""

    def _setup_with_witherbloom(self, num_extra_creatures: int = 2):
        """Create a game with Witherbloom on battlefield plus some creatures."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        extras = [
            Creature(name=f"Elf{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(num_extra_creatures)
        ]
        # Witherbloom is on the battlefield too (counts as a creature)
        set_board_state(game, 0, battlefield=[witherbloom] + extras)
        return game, p1, witherbloom

    def test_instant_gets_affinity(self) -> None:
        game, p1, witherbloom = self._setup_with_witherbloom(num_extra_creatures=2)
        # battlefield has witherbloom + 2 elves = 3 creatures
        spell = Instant(name="Shock", mana_cost=ManaCost.parse("{3}"),
                        owner=p1, controller=p1)
        reduction = get_cost_reduction(game, spell, p1)
        assert reduction == 3

    def test_sorcery_gets_affinity(self) -> None:
        game, p1, witherbloom = self._setup_with_witherbloom(num_extra_creatures=2)
        spell = Sorcery(name="Fireball", mana_cost=ManaCost.parse("{5}"),
                        owner=p1, controller=p1)
        reduction = get_cost_reduction(game, spell, p1)
        assert reduction == 3

    def test_opponent_instant_no_affinity(self) -> None:
        """Witherbloom's static does NOT apply to opponent's spells."""
        game, p1, witherbloom = self._setup_with_witherbloom(num_extra_creatures=2)
        p2 = game.players[1]
        spell = Instant(name="Counter", mana_cost=ManaCost.parse("{4}"),
                        owner=p2, controller=p2)
        # p2 has no creatures, and Witherbloom doesn't grant to opponents
        reduction = get_cost_reduction(game, spell, p2)
        assert reduction == 0

    def test_creature_spell_no_external_grant(self) -> None:
        """Witherbloom's static only applies to instants/sorceries, not creatures."""
        game, p1, witherbloom = self._setup_with_witherbloom(num_extra_creatures=2)
        # A creature that has no own cost_reduction()
        another_creature = Creature(
            name="Plain Creature", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{4}"), owner=p1, controller=p1
        )
        reduction = get_cost_reduction(game, another_creature, p1)
        assert reduction == 0

    def test_granted_affinity_respects_generic_cap(self) -> None:
        """Reduction can't exceed the spell's generic mana cost."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        extras = [
            Creature(name=f"E{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + extras)
        # 6 creatures total, spell only has 2 generic
        spell = Instant(name="Small Spell", mana_cost=ManaCost.parse("{2}{U}"),
                        owner=p1, controller=p1)
        reduction = get_cost_reduction(game, spell, p1)
        assert reduction == 2  # Capped at generic portion (2)

    def test_no_witherbloom_no_external_grant(self) -> None:
        """Without Witherbloom on battlefield, instants don't get external affinity."""
        game = create_game()
        p1 = game.players[0]
        extras = [
            Creature(name=f"C{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=extras)
        spell = Instant(name="Shock", mana_cost=ManaCost.parse("{3}"),
                        owner=p1, controller=p1)
        reduction = get_cost_reduction(game, spell, p1)
        assert reduction == 0

    def test_witherbloom_counts_itself_for_granted_affinity(self) -> None:
        """Witherbloom on battlefield counts itself as a creature for the grant."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        # Only Witherbloom itself, so 1 creature
        spell = Instant(name="Cantrip", mana_cost=ManaCost.parse("{2}"),
                        owner=p1, controller=p1)
        reduction = get_cost_reduction(game, spell, p1)
        assert reduction == 1

    def test_full_cast_instant_with_reduced_cost(self) -> None:
        """Integration: controller can cast instant at reduced cost thanks to Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        extras = [
            Creature(name=f"Elf{i}", base_power=1, base_toughness=1,
                     owner=p1, controller=p1)
            for i in range(2)
        ]
        # 3 creatures total → 3 reduction
        spell = Instant(name="Lava Burst", mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(
            game, 0,
            battlefield=[witherbloom] + extras,
            hand=[spell],
            mana={ManaType.RED: 1},  # Only {R} — after 3 generic reduction, that's enough
        )
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        cast_spell(game, p1, spell)
        # Spell should be on the stack (not fail due to mana)
        assert not game.stack.is_empty()
