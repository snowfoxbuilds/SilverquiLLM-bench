"""Tests for sos_245 — Witherbloom, the Balancer.

Witherbloom, the Balancer is a Legendary Creature — Elder Dragon with mana
cost {6}{B}{G}, 5/5, Flying, Deathtouch.

Oracle text:
  "Affinity for creatures (This spell costs {1} less to cast for each
   creature you control.)
   Flying, deathtouch
   Instant and sorcery spells you cast have affinity for creatures."

Test categories:
  1. Static card properties (name, mana cost, P/T, type, subtypes, supertypes)
  2. Keyword presence — Flying and Deathtouch
  3. Affinity for creatures: cost_reduction() counts own creatures on battlefield
  4. Affinity for creatures: with zero creatures, reduction is 0
  5. Affinity for creatures: counts only controller's creatures, not opponent's
  6. Affinity for creatures: generic cost cannot go below 0 (clamping)
  7. Instant and sorcery grant: when Witherbloom is on the battlefield,
     instants/sorceries cast by the controller benefit from the creature count
  8. Non-instant/non-sorcery spells do NOT get affinity from Witherbloom
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vanilla_creature(
    name: str = "TestCreature",
    owner: Any = None,
    power: int = 2,
    toughness: int = 2,
) -> Creature:
    """Return a minimal Creature instance owned/controlled by *owner*."""
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=power,
        base_toughness=toughness,
    )


def _make_instant(
    name: str = "TestInstant",
    cost_str: str = "{5}",
    owner: Any = None,
) -> Instant:
    """Return a minimal Instant with the given mana cost."""
    return Instant(
        name=name,
        mana_cost=ManaCost.parse(cost_str),
        owner=owner,
        controller=owner,
    )


def _make_sorcery(
    name: str = "TestSorcery",
    cost_str: str = "{4}",
    owner: Any = None,
) -> Sorcery:
    """Return a minimal Sorcery with the given mana cost."""
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse(cost_str),
        owner=owner,
        controller=owner,
    )


# ---------------------------------------------------------------------------
# 1. Static card properties
# ---------------------------------------------------------------------------


class TestWitherbloomTheBalancerProperties:
    """Static card data must match the sos_245 spec."""

    def test_is_creature_subclass(self) -> None:
        """WitherbloomTheBalancer must be a Creature instance."""
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_mana_cost_cmc(self) -> None:
        """Total converted mana cost must be 8 ({6}{B}{G} = 6+1+1)."""
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost.cmc == 8

    def test_base_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_base_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_card_type_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_legendary_supertype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_elder(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes

    def test_subtype_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# 2. Keyword presence — Flying and Deathtouch
# ---------------------------------------------------------------------------


class TestWitherbloomKeywords:
    """Flying and Deathtouch keywords must be present."""

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_flying_and_deathtouch_both_set(self) -> None:
        """Both keywords must be set simultaneously."""
        card = WitherbloomTheBalancer(owner=None)
        assert (Keyword.FLYING | Keyword.DEATHTOUCH) & card.keywords == (
            Keyword.FLYING | Keyword.DEATHTOUCH
        )


# ---------------------------------------------------------------------------
# 3. Affinity for creatures — Witherbloom's own cost_reduction()
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityForCreatures:
    """cost_reduction() returns {1} per creature the controller controls
    on the battlefield."""

    def test_no_creatures_gives_zero_reduction(self) -> None:
        """With no creatures on the battlefield, cost_reduction() returns 0."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_gives_reduction_of_one(self) -> None:
        """One creature on controller's battlefield → reduction of 1."""
        game = create_game()
        p1 = game.players[0]
        bear = _make_vanilla_creature(name="Bear", owner=p1)
        set_board_state(game, 0, battlefield=[bear])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_three_creatures_gives_reduction_of_three(self) -> None:
        """Three creatures on controller's battlefield → reduction of 3."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_six_creatures_gives_reduction_of_six(self) -> None:
        """Six creatures on controller's battlefield → reduction of 6
        (= full generic {6} of Witherbloom's cost)."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(6)
        ]
        set_board_state(game, 0, battlefield=creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 6


# ---------------------------------------------------------------------------
# 4. Affinity: cost cannot go below zero (clamping via get_cost_reduction)
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityClamping:
    """The engine clamps generic cost reduction so the generic portion
    cannot go below 0.  get_cost_reduction() enforces this contract."""

    def test_more_creatures_than_generic_clamps_to_generic(self) -> None:
        """10 creatures with generic {6} — reduction must clamp to 6, not 10."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # get_cost_reduction clamps to the generic portion of the mana cost.
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, card, p1)
        assert reduction == 6  # generic portion of {6}{B}{G}

    def test_cost_reduction_never_negative(self) -> None:
        """cost_reduction() itself must return a non-negative value."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) >= 0


# ---------------------------------------------------------------------------
# 5. Affinity: counts only controller's creatures, not opponent's
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityCountsOwn:
    """Affinity for creatures counts only creatures the *controller* controls.
    Opponent's creatures do not contribute to the cost reduction."""

    def test_only_controller_creatures_are_counted(self) -> None:
        """Opponent has 3 creatures; controller has 1. Reduction must be 1."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Controller has 1 creature
        my_creature = _make_vanilla_creature(name="MyBear", owner=p1)
        set_board_state(game, 0, battlefield=[my_creature])
        # Opponent has 3 creatures
        opp_creatures = [
            _make_vanilla_creature(name=f"OppCreature{i}", owner=p2) for i in range(3)
        ]
        set_board_state(game, 1, battlefield=opp_creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_no_controller_creatures_even_with_opponent_creatures(self) -> None:
        """Opponent has creatures but controller has none → reduction of 0."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        opp_creatures = [
            _make_vanilla_creature(name=f"OppCreature{i}", owner=p2) for i in range(5)
        ]
        set_board_state(game, 1, battlefield=opp_creatures)
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# 6. Instant/sorcery spells cast by controller get affinity for creatures
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinityToInstantsSorceries:
    """When Witherbloom is on the controller's battlefield, instants and
    sorceries cast by that controller benefit from affinity for creatures
    (i.e. their effective casting cost is reduced by the creature count).

    The expected mechanism: some hook on the game/casting pipeline checks
    for Witherbloom on the battlefield and supplements the spell's
    cost_reduction.
    """

    def test_instant_gets_cost_reduction_from_creature_count(self) -> None:
        """An instant cast with Witherbloom on the battlefield gets {1} less
        per creature the controller controls."""
        game = create_game()
        p1 = game.players[0]
        # Put Witherbloom on the battlefield
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Add 3 vanilla creatures (total 4 permanents on battlefield when
        # the cost is being calculated, including Witherbloom itself)
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(3)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + creatures)
        # Witherbloom must register its triggers/effects after being placed
        witherbloom.register_triggers(game)

        # A simple instant with generic cost {5}
        instant = _make_instant(name="TestInstant", cost_str="{5}", owner=p1)
        # Effective reduction: 4 creatures (witherbloom itself + 3) = 4
        effective_reduction = get_cost_reduction(game, instant, p1)
        assert effective_reduction == 4

    def test_sorcery_gets_cost_reduction_from_creature_count(self) -> None:
        """A sorcery cast with Witherbloom on the battlefield gets {1} less
        per creature the controller controls."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(2)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + creatures)
        witherbloom.register_triggers(game)

        sorcery = _make_sorcery(name="TestSorcery", cost_str="{6}", owner=p1)
        # 3 creatures total → reduction of 3
        effective_reduction = get_cost_reduction(game, sorcery, p1)
        assert effective_reduction == 3

    def test_no_affinity_without_witherbloom_on_battlefield(self) -> None:
        """Without Witherbloom on the battlefield, instants get no bonus
        from the creature count (beyond their own cost_reduction, which is 0
        by default for a vanilla instant)."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # No Witherbloom — vanilla instant has no cost_reduction of its own.
        instant = _make_instant(name="TestInstant", cost_str="{5}", owner=p1)
        effective_reduction = get_cost_reduction(game, instant, p1)
        assert effective_reduction == 0

    def test_instant_affinity_uses_controller_creatures_not_opponent(self) -> None:
        """Affinity granted to instants uses the *controller's* creature count."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Controller has 1 other creature (+ Witherbloom = 2 total)
        my_creature = _make_vanilla_creature(name="MyBear", owner=p1)
        set_board_state(game, 0, battlefield=[witherbloom, my_creature])
        # Opponent has 5 creatures
        opp_creatures = [
            _make_vanilla_creature(name=f"OppCreature{i}", owner=p2) for i in range(5)
        ]
        set_board_state(game, 1, battlefield=opp_creatures)
        witherbloom.register_triggers(game)

        instant = _make_instant(name="TestInstant", cost_str="{5}", owner=p1)
        # Only controller's 2 creatures contribute
        effective_reduction = get_cost_reduction(game, instant, p1)
        assert effective_reduction == 2

    def test_affinity_granted_to_instant_cast_succeeds_with_reduced_mana(self) -> None:
        """Functional test: casting an instant with Witherbloom on the battlefield
        succeeds with less mana than the printed cost when creatures are present."""
        from engine.casting import cast_spell as engine_cast_spell
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]

        # Witherbloom + 2 creatures on battlefield → reduction of 3
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(2)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + creatures)
        witherbloom.register_triggers(game)

        # Put an instant with cost {5} in hand.
        instant = _make_instant(name="TestInstant", cost_str="{5}", owner=p1)
        set_board_state(game, 0, hand=[instant])

        # Fund the player with only {2} — not enough WITHOUT affinity,
        # but with 3 creatures (reduction=3) the effective cost is {5-3}={2}.
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        # Set up sorcery-speed timing (instants can be cast anytime, but
        # ensure active player is set correctly).
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Should NOT raise — reduced cost is exactly payable.
        from engine.casting import CastingError
        try:
            engine_cast_spell(game, p1, instant)
        except CastingError as e:
            pytest.fail(
                f"Casting should succeed with reduced cost, but got: {e}"
            )


# ---------------------------------------------------------------------------
# 7. Non-instant/non-sorcery spells do NOT get affinity from Witherbloom
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinityOnlyToInstantsSorceries:
    """Witherbloom's "Instant and sorcery spells you cast have affinity"
    ability does NOT apply to creature spells, enchantments, artifacts, etc."""

    def test_creature_spell_does_not_get_bonus_from_witherbloom(self) -> None:
        """A creature spell cast while Witherbloom is on the battlefield
        does NOT receive the creature-count cost reduction (only instants
        and sorceries are granted affinity)."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            _make_vanilla_creature(name=f"Creature{i}", owner=p1) for i in range(3)
        ]
        set_board_state(game, 0, battlefield=[witherbloom] + creatures)
        witherbloom.register_triggers(game)

        # A creature spell has no cost_reduction by default.
        creature_spell = _make_vanilla_creature(
            name="NewCreature", owner=p1, power=3, toughness=3
        )
        creature_spell.mana_cost = ManaCost.parse("{5}")
        effective_reduction = get_cost_reduction(game, creature_spell, p1)
        assert effective_reduction == 0, (
            "Creature spells must NOT get affinity for creatures from Witherbloom"
        )
