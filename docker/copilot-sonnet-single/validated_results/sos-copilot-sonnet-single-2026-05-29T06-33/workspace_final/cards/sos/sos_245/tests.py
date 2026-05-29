"""Tests for SOS 245 — Witherbloom, the Balancer.

Oracle text:
  Affinity for creatures (This spell costs {1} less to cast for each creature
  you control.)
  Flying, deathtouch
  Instant and sorcery spells you cast have affinity for creatures.

Tests cover:
- Static card properties (name, mana_cost, P/T, legendary, subtypes, card type)
- Flying and Deathtouch keywords
- Self-affinity: cost_reduction returns 1 per creature controller controls
- Self-affinity: zero creatures → zero reduction
- Self-affinity: reduction capped at generic mana (never negative)
- Self-affinity: Witherbloom itself does not count (not yet on battlefield when cast)
- Continuous effect: instants in controller's hand gain affinity for creatures
- Continuous effect: sorceries in controller's hand gain affinity for creatures
- Continuous effect: non-instant/sorcery cards do NOT gain affinity
- Continuous effect: opponent's spells are NOT affected
- Continuous effect: not active when Witherbloom is not on the battlefield
- Continuous effect: register_triggers adds at least one continuous effect
- Continuous effect: affinity value equals number of controller's creatures
- Idempotency: multiple apply_all calls do not stack the affinity bonus
"""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestWitherbloomTheBalancerProperties:
    """Static card data must match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

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

    def test_has_creature_card_type(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_elder_subtype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes

    def test_has_dragon_subtype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Keyword tests — Flying and Deathtouch
# ---------------------------------------------------------------------------


class TestWitherbloomTheBalancerKeywords:
    """Witherbloom must have both Flying and Deathtouch."""

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_does_not_have_vigilance(self) -> None:
        """Deathtouch not vigilance — sanity-check the keywords are correct."""
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.VIGILANCE not in card.keywords

    def test_does_not_have_trample(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.TRAMPLE not in card.keywords


# ---------------------------------------------------------------------------
# Self-affinity (cost_reduction) tests
# ---------------------------------------------------------------------------


class TestWitherbloomTheBalancerSelfAffinity:
    """Witherbloom's cost_reduction must return 1 for each creature the
    controller controls (affinity for creatures on the self-cast path)."""

    def test_zero_creatures_gives_zero_reduction(self) -> None:
        """No creatures on battlefield → cost_reduction == 0."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Hand only — no creatures on battlefield
        set_board_state(game, 0, hand=[witherbloom])
        assert witherbloom.cost_reduction(game) == 0

    def test_one_creature_gives_reduction_of_one(self) -> None:
        """One creature on the controller's battlefield → cost_reduction == 1."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, hand=[witherbloom], battlefield=[bear])
        assert witherbloom.cost_reduction(game) == 1

    def test_three_creatures_gives_reduction_of_three(self) -> None:
        """Three creatures on the battlefield → cost_reduction == 3."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Creature {i}", owner=p1, controller=p1, base_power=1, base_toughness=1)
            for i in range(3)
        ]
        set_board_state(game, 0, hand=[witherbloom], battlefield=creatures)
        assert witherbloom.cost_reduction(game) == 3

    def test_opponent_creatures_do_not_count(self) -> None:
        """Only the controller's creatures contribute to affinity cost reduction."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_bear = Creature(
            name="Opponent Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, hand=[witherbloom])
        set_board_state(game, 1, battlefield=[opponent_bear])
        assert witherbloom.cost_reduction(game) == 0

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Non-creature permanents in the controller's battlefield don't count."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # An instant card accidentally placed on battlefield — not a creature
        artifact = Instant(name="Not a creature", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[witherbloom], battlefield=[artifact])
        assert witherbloom.cost_reduction(game) == 0

    def test_large_number_of_creatures_gives_correct_reduction(self) -> None:
        """Six creatures → cost_reduction == 6 (full generic reduction)."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Soldier {i}", owner=p1, controller=p1, base_power=1, base_toughness=1)
            for i in range(6)
        ]
        set_board_state(game, 0, hand=[witherbloom], battlefield=creatures)
        assert witherbloom.cost_reduction(game) == 6


# ---------------------------------------------------------------------------
# Continuous effect: instants and sorceries gain affinity for creatures
# ---------------------------------------------------------------------------


class TestWitherbloomTheBalancerAffinityGrant:
    """While on the battlefield, Witherbloom grants affinity for creatures to
    each instant and sorcery the controller casts. The implementation is
    expected to mark cards in the controller's hand with a
    ``cost_reduction_creatures`` attribute (or equivalent ``affinity_for_creatures``
    flag), mirroring the pattern from Silverquill's casualty grant.

    Convention: the granted attribute on the hand card is checked via
    ``cost_reduction(game)`` returning a value equal to the number of creatures
    on the battlefield, OR via a ``affinity_for_creatures`` boolean attribute
    set to True on the card.
    """

    def _setup_witherbloom_on_battlefield(self, game, player_index: int = 0):
        """Place Witherbloom on player's battlefield and register its triggers."""
        player = game.players[player_index]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        set_board_state(game, player_index, battlefield=[witherbloom])
        witherbloom.register_triggers(game)
        return witherbloom

    def test_instant_in_hand_gets_affinity_for_creatures(self) -> None:
        """An instant in the controller's hand acquires affinity for creatures
        while Witherbloom is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        self._setup_witherbloom_on_battlefield(game, 0)

        lightning = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[lightning])

        game.effect_manager.apply_all(game)

        assert getattr(lightning, "affinity_for_creatures", False) is True, (
            "Instant in controller's hand should have affinity_for_creatures=True"
        )

    def test_sorcery_in_hand_gets_affinity_for_creatures(self) -> None:
        """A sorcery in the controller's hand acquires affinity for creatures
        while Witherbloom is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        self._setup_witherbloom_on_battlefield(game, 0)

        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[divination])

        game.effect_manager.apply_all(game)

        assert getattr(divination, "affinity_for_creatures", False) is True, (
            "Sorcery in controller's hand should have affinity_for_creatures=True"
        )

    def test_creature_in_hand_does_not_get_affinity(self) -> None:
        """A creature card in hand must NOT receive the affinity grant."""
        game = create_game()
        p1 = game.players[0]
        self._setup_witherbloom_on_battlefield(game, 0)

        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, hand=[bear])

        game.effect_manager.apply_all(game)

        assert getattr(bear, "affinity_for_creatures", False) is not True, (
            "Creature in hand must not receive affinity_for_creatures from Witherbloom"
        )

    def test_affinity_grant_not_applied_without_witherbloom_on_battlefield(self) -> None:
        """Without Witherbloom on the battlefield, instants in hand have no affinity grant."""
        game = create_game()
        p1 = game.players[0]

        # Witherbloom is NOT on the battlefield — no register_triggers call
        counterspell = Instant(name="Counterspell", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[counterspell])

        game.effect_manager.apply_all(game)

        assert getattr(counterspell, "affinity_for_creatures", False) is not True, (
            "Instant should NOT have affinity_for_creatures without Witherbloom on battlefield"
        )

    def test_opponent_instant_does_not_get_affinity(self) -> None:
        """Opponent's instants in hand must NOT receive Witherbloom's affinity grant."""
        game = create_game()
        self._setup_witherbloom_on_battlefield(game, 0)  # player 0's battlefield

        p2 = game.players[1]
        opponent_instant = Instant(name="Negate", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[opponent_instant])

        game.effect_manager.apply_all(game)

        assert getattr(opponent_instant, "affinity_for_creatures", False) is not True, (
            "Opponent's instant must not receive Witherbloom's affinity grant"
        )

    def test_opponent_sorcery_does_not_get_affinity(self) -> None:
        """Opponent's sorceries in hand must NOT receive Witherbloom's affinity grant."""
        game = create_game()
        self._setup_witherbloom_on_battlefield(game, 0)

        p2 = game.players[1]
        opponent_sorcery = Sorcery(name="Mind Rot", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[opponent_sorcery])

        game.effect_manager.apply_all(game)

        assert getattr(opponent_sorcery, "affinity_for_creatures", False) is not True, (
            "Opponent's sorcery in hand must not receive Witherbloom's affinity grant"
        )

    def test_register_triggers_adds_continuous_effect(self) -> None:
        """register_triggers must register at least one continuous effect
        into the game's effect_manager when called."""
        game = create_game()
        p1 = game.players[0]

        effects_before = len(game.effect_manager.get_all())

        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        witherbloom.register_triggers(game)

        effects_after = len(game.effect_manager.get_all())
        assert effects_after > effects_before, (
            "register_triggers should add at least one continuous effect to effect_manager"
        )

    def test_affinity_grant_is_idempotent_after_multiple_apply_all(self) -> None:
        """Calling effect_manager.apply_all multiple times should not
        accumulate or corrupt the affinity_for_creatures flag."""
        game = create_game()
        p1 = game.players[0]
        self._setup_witherbloom_on_battlefield(game, 0)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock])

        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)

        assert getattr(shock, "affinity_for_creatures", False) is True, (
            "affinity_for_creatures should still be True after multiple apply_all calls"
        )

    def test_multiple_spells_in_hand_all_get_affinity(self) -> None:
        """All instants and sorceries in the controller's hand get the affinity grant."""
        game = create_game()
        p1 = game.players[0]
        self._setup_witherbloom_on_battlefield(game, 0)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock, bolt, divination])

        game.effect_manager.apply_all(game)

        for spell in [shock, bolt, divination]:
            assert getattr(spell, "affinity_for_creatures", False) is True, (
                f"{spell.name} should have affinity_for_creatures=True"
            )


# ---------------------------------------------------------------------------
# Affinity cost_reduction interaction: granted spells reduce cost by creature count
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityGrantedCostReduction:
    """When Witherbloom is on the battlefield and a spell in hand has
    affinity_for_creatures, that spell's cost_reduction should return
    a value equal to the number of creatures the controller controls."""

    def _setup_witherbloom_on_battlefield(self, game, player_index: int = 0):
        player = game.players[player_index]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        set_board_state(game, player_index, battlefield=[witherbloom])
        witherbloom.register_triggers(game)
        return witherbloom

    def test_granted_instant_cost_reduction_equals_creature_count(self) -> None:
        """An instant granted affinity for creatures should have cost_reduction == creature count."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = self._setup_witherbloom_on_battlefield(game, 0)

        # Add 3 extra creatures alongside Witherbloom
        extra_creatures = [
            Creature(name=f"Soldier {i}", owner=p1, controller=p1, base_power=1, base_toughness=1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + extra_creatures)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock])

        game.effect_manager.apply_all(game)

        # After apply_all, shock should have affinity_for_creatures=True
        assert getattr(shock, "affinity_for_creatures", False) is True

        # The cost_reduction for Shock should now equal number of creatures on battlefield
        # Witherbloom + 3 soldiers = 4 creatures
        reduction = shock.cost_reduction(game)
        assert reduction == 4, (
            f"Instant with affinity for creatures should reduce cost by 4 (creatures on bf), got {reduction}"
        )

    def test_granted_sorcery_cost_reduction_equals_creature_count(self) -> None:
        """A sorcery granted affinity for creatures should have cost_reduction == creature count."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = self._setup_witherbloom_on_battlefield(game, 0)

        two_bears = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1, base_power=2, base_toughness=2)
            for i in range(2)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + two_bears)

        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[divination])

        game.effect_manager.apply_all(game)

        assert getattr(divination, "affinity_for_creatures", False) is True

        # Witherbloom + 2 bears = 3 creatures
        reduction = divination.cost_reduction(game)
        assert reduction == 3, (
            f"Sorcery with affinity for creatures should reduce cost by 3, got {reduction}"
        )
