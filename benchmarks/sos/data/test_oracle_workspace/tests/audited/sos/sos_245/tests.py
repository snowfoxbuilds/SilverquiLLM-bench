"""Audited tests for Witherbloom, the Balancer (sos_245).

Oracle: {6}{B}{G} 5/5 Legendary Creature — Elder Dragon.
  Affinity for creatures (This spell costs {1} less to cast for each creature
  you control.)
  Flying, deathtouch
  Instant and sorcery spells you cast have affinity for creatures.

Simulation-only shape (AUDITED-TEST-API.md): affinity cost reduction is
oracle-only mechanics, so it is exercised indirectly — the subject spell is
cast under the grant and the reduced-cost outcome is asserted through
mana-minimality (the pool holds exactly the reduced cost, or one less for the
``perform_illegal_action`` negative).  Flying and deathtouch are asserted
behaviourally through combat outcomes; illegal blocks are silently filtered
by the engine, so block illegality is asserted by outcome (the flyer's damage
reached the player).

Tests:
  1. test_card_identity
  2. test_own_affinity_reduces_cost_by_creature_count
  3. test_own_affinity_reduction_is_not_one_more
  4. test_own_affinity_clamps_at_generic_portion
  5. test_granted_affinity_reduces_instant_cost
  6. test_granted_affinity_reduction_is_not_one_more
  7. test_grant_does_not_apply_to_creature_spells
  8. test_grant_does_not_apply_to_opponents_spells
  9. test_flying_evades_ground_blocker_by_outcome
  10. test_deathtouch_fells_tough_blocker_by_outcome
"""

from __future__ import annotations

from card_impl import WitherbloomTheBalancer

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_damage,
    assert_in_zone,
    assert_life_total,
    assert_mana_pool,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Witherbloom, the Balancer"


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Token {i}", base_power=1, base_toughness=1)
        for i in range(n)
    ]


def _cast_as_p0(game, name, mana, directive) -> None:
    set_board_state(game, 0, mana=mana)
    set_player(game, 0, DeterministicPlayer("P0", script=[
        directive(CastSpell(name)),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
    priority_loop(game)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = WitherbloomTheBalancer()
        assert card.name == _NAME
        assert card.mana_cost.generic == 6
        assert card.mana_cost.pips.get(ManaType.BLACK) == 1
        assert card.mana_cost.pips.get(ManaType.GREEN) == 1
        assert card.mana_cost.cmc == 8
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestOwnAffinity:
    """Affinity for creatures on Witherbloom itself, via mana-minimality."""

    def test_own_affinity_reduces_cost_by_creature_count(self) -> None:
        """Three creatures → {6}{B}{G} casts for exactly {3}{B}{G}."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        set_board_state(game, 0, battlefield=_bears(3), hand=[WitherbloomTheBalancer()])

        _cast_as_p0(
            game, _NAME,
            {ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
            perform_action,
        )

        assert_in_zone(game, 0, Zone.BATTLEFIELD, _NAME)
        assert_mana_pool(game, 0, {})

    def test_own_affinity_reduction_is_not_one_more(self) -> None:
        """With three creatures, one mana short of {3}{B}{G} is rejected."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        set_board_state(game, 0, battlefield=_bears(3), hand=[WitherbloomTheBalancer()])

        _cast_as_p0(
            game, _NAME,
            {ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
            perform_illegal_action,
        )

        assert_in_zone(game, 0, Zone.HAND, _NAME)

    def test_own_affinity_clamps_at_generic_portion(self) -> None:
        """Ten creatures cannot reduce below {B}{G} — the colored pips stay."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        set_board_state(game, 0, battlefield=_bears(10), hand=[WitherbloomTheBalancer()])

        _cast_as_p0(
            game, _NAME,
            {ManaType.BLACK: 1, ManaType.GREEN: 1},
            perform_action,
        )

        assert_in_zone(game, 0, Zone.BATTLEFIELD, _NAME)
        assert_mana_pool(game, 0, {})


class TestGrantedAffinity:
    """Instant and sorcery spells you cast have affinity for creatures."""

    def test_granted_affinity_reduces_instant_cost(self) -> None:
        """Witherbloom + two creatures (three total) reduce a {4}{R} instant
        to exactly {1}{R}."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        big_bolt = Instant(
            name="Big Bolt", mana_cost=ManaCost(generic=4, pips={ManaType.RED: 1}),
        )
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(), *_bears(2)],
            hand=[big_bolt],
        )

        _cast_as_p0(
            game, "Big Bolt",
            {ManaType.COLORLESS: 1, ManaType.RED: 1},
            perform_action,
        )

        assert_in_zone(game, 0, Zone.GRAVEYARD, "Big Bolt")
        assert_mana_pool(game, 0, {})

    def test_granted_affinity_reduction_is_not_one_more(self) -> None:
        """The grant reduces only the generic portion: {R} alone cannot pay
        the reduced {1}{R}."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        big_bolt = Instant(
            name="Big Bolt", mana_cost=ManaCost(generic=4, pips={ManaType.RED: 1}),
        )
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(), *_bears(2)],
            hand=[big_bolt],
        )

        _cast_as_p0(game, "Big Bolt", {ManaType.RED: 1}, perform_illegal_action)

        assert_in_zone(game, 0, Zone.HAND, "Big Bolt")

    def test_grant_does_not_apply_to_creature_spells(self) -> None:
        """A {3} creature does not become free under three creatures — the
        grant is instants/sorceries only."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        bear = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            mana_cost=ManaCost(generic=3),
        )
        set_board_state(
            game, 0,
            battlefield=[WitherbloomTheBalancer(), *_bears(2)],
            hand=[bear],
        )

        _cast_as_p0(game, "Grizzly Bears", {}, perform_illegal_action)

        assert_in_zone(game, 0, Zone.HAND, "Grizzly Bears")

    def test_grant_does_not_apply_to_opponents_spells(self) -> None:
        """The opponent's instants get no reduction from your Witherbloom —
        with two creatures of their own, a {2} instant from an empty pool is
        still rejected."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        cheap_trick = Instant(name="Cheap Trick", mana_cost=ManaCost(generic=2))
        set_board_state(game, 0, battlefield=[WitherbloomTheBalancer(), *_bears(2)])
        set_board_state(game, 1, battlefield=_bears(2), hand=[cheap_trick])

        set_player(game, 0, DeterministicPlayer("P0", script=[no_op(), no_op()]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_illegal_action(CastSpell("Cheap Trick")),
        ]))
        priority_loop(game)

        assert_in_zone(game, 1, Zone.HAND, "Cheap Trick")


class TestCombatKeywordsByOutcome:
    """Flying / deathtouch asserted through combat outcomes (illegal blocks
    are silently filtered, so block illegality is asserted by outcome)."""

    def test_flying_evades_ground_blocker_by_outcome(self) -> None:
        """A ground creature's block of the 5/5 flyer is dropped — the
        flyer's damage reaches the player and the would-be blocker takes
        nothing."""
        game = create_game()
        witherbloom = WitherbloomTheBalancer()
        wall = Creature(name="Wall", base_power=0, base_toughness=8)
        set_board_state(game, 0, battlefield=[witherbloom])
        set_board_state(game, 1, battlefield=[wall])
        set_player(game, 0, DeterministicPlayer("P0", choices=[[witherbloom]]))
        set_player(game, 1, DeterministicPlayer("P1", choices=[{wall: witherbloom}]))

        advance_to_phase(game, Phase.COMBAT, Step.COMBAT_DAMAGE)

        assert_life_total(game, 1, 15)
        assert_damage(game, wall, 0)
        assert_damage(game, witherbloom, 0)

    def test_deathtouch_fells_tough_blocker_by_outcome(self) -> None:
        """A 2/8 reach blocker legally blocks the flyer and would survive 5
        damage — deathtouch makes it lethal anyway."""
        game = create_game()
        witherbloom = WitherbloomTheBalancer()
        guard = Creature(
            name="Reach Guard", base_power=2, base_toughness=8,
            keywords=Keyword.REACH,
        )
        set_board_state(game, 0, battlefield=[witherbloom])
        set_board_state(game, 1, battlefield=[guard])
        set_player(game, 0, DeterministicPlayer("P0", choices=[[witherbloom]]))
        set_player(game, 1, DeterministicPlayer("P1", choices=[{guard: witherbloom}]))

        advance_to_phase(game, Phase.COMBAT, Step.COMBAT_DAMAGE)

        assert_in_zone(game, 1, Zone.GRAVEYARD, "Reach Guard")
        assert_damage(game, witherbloom, 2)
        assert_life_total(game, 1, 20)
