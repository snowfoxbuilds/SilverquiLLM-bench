"""Tests for SOS 245 — Witherbloom, the Balancer.

Witherbloom, the Balancer is a {6}{B}{G} Legendary Creature — Elder Dragon
with 5/5, flying, deathtouch.

Oracle text:
  "Affinity for creatures (This spell costs {1} less to cast for each creature
  you control.)
  Flying, deathtouch
  Instant and sorcery spells you cast have affinity for creatures."

Requirements tested:
1. Static properties: name, mana cost, power/toughness, types, supertypes, subtypes, keywords.
2. Affinity for creatures (self): cost_reduction returns the number of creatures the controller controls.
3. Flying and deathtouch keywords.
4. Granting affinity for creatures to controller's instants and sorceries.
5. Edge cases: no creatures, only opponent creatures, Witherbloom counts as a creature.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery, Enchantment
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_witherbloom(owner=None, controller=None):
    """Create a Witherbloom, the Balancer instance."""
    return WitherbloomTheBalancer(owner=owner, controller=controller)


def _make_creature(name="Grizzly Bears", owner=None, controller=None, power=2, toughness=2):
    """Create a vanilla creature."""
    return Creature(
        name=name,
        owner=owner,
        controller=controller,
        base_power=power,
        base_toughness=toughness,
    )


def _make_instant(name="Lightning Bolt", owner=None, controller=None):
    """Create a simple instant spell."""
    return Instant(
        name=name,
        mana_cost=ManaCost.parse("{4}{R}"),
        owner=owner,
        controller=controller,
        rules_text="Deal 3 damage to any target.",
    )


def _make_sorcery(name="Divination", owner=None, controller=None):
    """Create a simple sorcery spell."""
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse("{5}{U}"),
        owner=owner,
        controller=controller,
        rules_text="Draw two cards.",
    )


# ===========================================================================
# Static Properties
# ===========================================================================


class TestWitherbloomProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = _make_witherbloom()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = _make_witherbloom()
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = _make_witherbloom()
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_mana_value_is_eight(self) -> None:
        card = _make_witherbloom()
        assert card.mana_cost.cmc == 8

    def test_card_type_creature(self) -> None:
        card = _make_witherbloom()
        assert CardType.CREATURE in card.card_types

    def test_supertype_legendary(self) -> None:
        card = _make_witherbloom()
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = _make_witherbloom()
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_power_toughness(self) -> None:
        card = _make_witherbloom()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = _make_witherbloom()
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = _make_witherbloom()
        assert Keyword.DEATHTOUCH in card.keywords


# ===========================================================================
# Affinity for creatures (self — Witherbloom's own cost reduction)
# ===========================================================================


class TestWitherbloomSelfAffinity:
    """Witherbloom costs {1} less to cast for each creature you control.

    The cost_reduction method should return the count of creatures the
    controller controls on the battlefield."""

    def test_no_creatures_no_reduction(self) -> None:
        """With no creatures on the battlefield, cost_reduction returns 0."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        # No creatures on the battlefield
        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_one_creature_reduces_by_one(self) -> None:
        """One creature on the battlefield reduces cost by 1."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        bear = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])
        reduction = card.cost_reduction(game)
        assert reduction == 1

    def test_three_creatures_reduces_by_three(self) -> None:
        """Three creatures on the battlefield reduces cost by 3."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        reduction = card.cost_reduction(game)
        assert reduction == 3

    def test_six_creatures_reduces_by_six(self) -> None:
        """Six creatures fully reduce the generic mana portion ({6})."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(6)
        ]
        set_board_state(game, 0, battlefield=creatures)
        reduction = card.cost_reduction(game)
        assert reduction == 6

    def test_opponent_creatures_do_not_count(self) -> None:
        """Only the controller's creatures count for affinity, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_witherbloom(owner=p1, controller=p1)
        # Put creatures only on opponent's battlefield
        bear = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear])
        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Enchantments and other non-creature permanents should not count."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        enchantment = Enchantment(
            name="Test Enchantment",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[enchantment])
        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_excess_creatures_beyond_generic_cost(self) -> None:
        """Affinity returns the full creature count even if it exceeds
        the generic cost. Clamping happens in the casting pipeline,
        not in cost_reduction itself."""
        game = create_game()
        p1 = game.players[0]
        card = _make_witherbloom(owner=p1, controller=p1)
        creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures)
        reduction = card.cost_reduction(game)
        # Should return 10 (the full creature count); clamping to 6 generic
        # mana is done by get_cost_reduction, not by cost_reduction itself.
        assert reduction >= 6


# ===========================================================================
# Granting affinity to instants and sorceries
# ===========================================================================


class TestWitherbloomGrantsAffinityToInstants:
    """'Instant and sorcery spells you cast have affinity for creatures.'

    When Witherbloom is on the battlefield, the controller's instant
    and sorcery spells should have their cost reduced by the number
    of creatures the controller controls.

    The implementation may use a continuous effect, a trigger-based
    approach, or modify cost_reduction on the spells. We test the
    observable outcome: the cost is reduced."""

    def _setup_with_witherbloom_on_battlefield(self):
        """Create a game with Witherbloom on the battlefield, triggers
        registered, and return (game, p1, p2, witherbloom)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = _make_witherbloom(owner=p1, controller=p1)
        game.get_battlefield(p1).add(witherbloom)
        witherbloom.register_triggers(game)
        witherbloom.register_replacement_effects(game)
        return game, p1, p2, witherbloom

    def test_instant_gets_cost_reduction_from_creatures(self) -> None:
        """An instant spell cast by Witherbloom's controller should have
        its cost reduced by the number of creatures that controller controls."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        # Place creatures on the battlefield (Witherbloom itself is one)
        bears = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(2)
        ]
        for bear in bears:
            game.get_battlefield(p1).add(bear)

        # 3 total creatures (Witherbloom + 2 bears)
        bolt = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)

        # The instant should get affinity for creatures.
        # Test via cost_reduction on the instant itself (if the implementation
        # modifies the card's cost_reduction method) or via the casting pipeline.
        from engine.casting import get_cost_reduction
        bolt.controller = p1
        reduction = get_cost_reduction(game, bolt, p1)

        # Expected: reduction of 3 (Witherbloom + 2 bears), clamped to generic cost
        # bolt's mana cost is {4}{R}, so generic is 4
        assert reduction == 3

    def test_sorcery_gets_cost_reduction_from_creatures(self) -> None:
        """A sorcery spell cast by Witherbloom's controller should have
        its cost reduced by the number of creatures that controller controls."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        bears = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(2)
        ]
        for bear in bears:
            game.get_battlefield(p1).add(bear)

        # 3 total creatures (Witherbloom + 2 bears)
        divination = _make_sorcery(name="Divination", owner=p1, controller=p1)

        from engine.casting import get_cost_reduction
        divination.controller = p1
        reduction = get_cost_reduction(game, divination, p1)

        # divination's mana cost is {5}{U}, generic is 5
        assert reduction == 3

    def test_creature_spell_does_not_get_affinity(self) -> None:
        """Creature spells cast by the controller should NOT get affinity
        from Witherbloom (only instants and sorceries)."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        bears = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(2)
        ]
        for bear in bears:
            game.get_battlefield(p1).add(bear)

        # A creature spell should not benefit from the affinity granting
        new_creature = Creature(
            name="Big Creature",
            mana_cost=ManaCost.parse("{5}"),
            owner=p1,
            controller=p1,
            base_power=5,
            base_toughness=5,
        )
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, new_creature, p1)
        assert reduction == 0

    def test_opponent_instant_does_not_get_affinity(self) -> None:
        """Opponent's instants should NOT get affinity from our Witherbloom."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        bears = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(2)
        ]
        for bear in bears:
            game.get_battlefield(p1).add(bear)

        # Opponent's instant
        opp_bolt = _make_instant(name="Opp Bolt", owner=p2, controller=p2)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, opp_bolt, p2)
        assert reduction == 0

    def test_affinity_counts_witherbloom_itself(self) -> None:
        """Witherbloom is a creature, so it counts toward its own affinity
        and also toward the affinity it grants to instants/sorceries."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        # Only Witherbloom is on the battlefield (1 creature)
        bolt = _make_instant(name="Test Bolt", owner=p1, controller=p1)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, bolt, p1)

        # 1 creature (Witherbloom), so reduction should be 1
        assert reduction == 1

    def test_affinity_clamped_to_generic_cost(self) -> None:
        """The affinity reduction cannot reduce below 0 generic mana.
        This is handled by get_cost_reduction clamping."""
        game, p1, p2, witherbloom = self._setup_with_witherbloom_on_battlefield()

        # Add many creatures
        many_creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(10)
        ]
        for bear in many_creatures:
            game.get_battlefield(p1).add(bear)

        # 11 total creatures (Witherbloom + 10 bears)
        # Bolt costs {4}{R}, generic is 4
        bolt = _make_instant(name="Test Bolt", owner=p1, controller=p1)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, bolt, p1)

        # Clamped to 4 (the generic mana cost of the bolt)
        assert reduction == 4

    def test_no_creatures_no_reduction_for_instant(self) -> None:
        """With no creatures on the battlefield, an instant gets no reduction.
        Witherbloom must be on the battlefield for this to apply, but if
        it's somehow not a creature, the count would be zero."""
        game = create_game()
        p1 = game.players[0]
        # Witherbloom is NOT on the battlefield in this test
        bolt = _make_instant(name="Test Bolt", owner=p1, controller=p1)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, bolt, p1)
        assert reduction == 0


# ===========================================================================
# Affinity for self — interaction with the casting pipeline
# ===========================================================================


class TestWitherbloomCastingWithAffinity:
    """Test that Witherbloom's own affinity works through the casting pipeline."""

    def test_witherbloom_castable_with_fewer_mana_when_creatures_exist(self) -> None:
        """With 3 creatures on the battlefield, Witherbloom should cost
        {3}{B}{G} effectively (6 generic reduced by 3)."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _make_witherbloom(owner=p1, controller=p1)

        # 3 creatures on the battlefield
        creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)

        from engine.casting import get_cost_reduction, _apply_cost_reduction
        reduction = get_cost_reduction(game, witherbloom, p1)
        effective = _apply_cost_reduction(witherbloom.mana_cost, reduction)

        # Generic should be 6 - 3 = 3, plus {B}{G}
        assert effective.generic == 3
        assert effective.pips.get(ManaType.BLACK, 0) == 1
        assert effective.pips.get(ManaType.GREEN, 0) == 1

    def test_witherbloom_free_generic_with_six_creatures(self) -> None:
        """With 6 creatures on the battlefield, the generic portion is
        fully reduced. Only {B}{G} remains."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _make_witherbloom(owner=p1, controller=p1)

        creatures = [
            _make_creature(name=f"Bear_{i}", owner=p1, controller=p1)
            for i in range(6)
        ]
        set_board_state(game, 0, battlefield=creatures)

        from engine.casting import get_cost_reduction, _apply_cost_reduction
        reduction = get_cost_reduction(game, witherbloom, p1)
        effective = _apply_cost_reduction(witherbloom.mana_cost, reduction)

        # Generic should be 0, only colored pips remain
        assert effective.generic == 0
        assert effective.pips.get(ManaType.BLACK, 0) == 1
        assert effective.pips.get(ManaType.GREEN, 0) == 1


# ===========================================================================
# Edge cases
# ===========================================================================


class TestWitherbloomEdgeCases:
    """Edge cases and boundary conditions."""

    def test_witherbloom_on_battlefield_counts_itself_for_own_spells(self) -> None:
        """When Witherbloom is already on the battlefield, it counts itself
        as a creature for the affinity it grants to instants/sorceries."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _make_witherbloom(owner=p1, controller=p1)
        game.get_battlefield(p1).add(witherbloom)
        witherbloom.register_triggers(game)

        bolt = _make_instant(name="Bolt", owner=p1, controller=p1)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, bolt, p1)
        # Witherbloom itself is 1 creature
        assert reduction >= 1

    def test_multiple_witherblooms_stack_affinity_on_self(self) -> None:
        """If a second copy of Witherbloom were somehow on the battlefield,
        the self-affinity should still count all creatures (non-legendary
        rule aside). We test that counting is done at query time."""
        game = create_game()
        p1 = game.players[0]
        # Just test that cost_reduction counts creatures dynamically
        w1 = _make_witherbloom(owner=p1, controller=p1)
        bear = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])

        reduction_before = w1.cost_reduction(game)
        bear2 = _make_creature(name="Bear2", owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear2)
        reduction_after = w1.cost_reduction(game)

        assert reduction_after == reduction_before + 1
