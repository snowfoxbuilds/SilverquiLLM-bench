"""Audited tests for Great Hall of the Biblioplex (sos_257).

Oracle: Land.
  {T}: Add {C}.
  {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to cast
      an instant or sorcery spell.
  {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      "Whenever you cast an instant or sorcery spell, this creature gets
      +1/+0 until end of turn."  It's still a land.

Simulation-only shape (AUDITED-TEST-API.md): abilities are activated by
printed-order index via ``ActivateAbility`` (mana abilities resolve straight
into the pool; the {5} animation uses the stack).  "Add one mana of any
color" is a player choice answered from the choice script (Channel 2) — the
tests float white.  The restricted mana is oracle-only mechanics, exercised
indirectly: a real cast paid from it either succeeds (instant) or is rejected
(creature, ``perform_illegal_action``).
The prowess-like boost is until-end-of-turn, so the reset is reached with
``advance_to_phase(ENDING, CLEANUP)`` — P/T asserted before and after.

Tests:
  1.  test_card_identity
  2.  test_first_ability_adds_colorless
  3.  test_second_ability_costs_life_and_taps
  4.  test_restricted_mana_pays_an_instant
  5.  test_restricted_mana_rejected_for_a_creature
  6.  test_animation_makes_a_2_4_wizard_that_is_still_a_land
  7.  test_animation_requires_five_mana
  8.  test_reanimation_is_a_gated_noop
  9.  test_boost_on_controller_instant_and_reset_at_cleanup
  10. test_opponent_spell_does_not_boost
  11. test_two_spells_stack_boosts
  12. test_no_boost_when_not_animated
"""

from __future__ import annotations

from card_impl import GreatHallOfTheBiblioplex

from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import (
    ActivateAbility,
    CastSpell,
    DeterministicPlayer,
    PlayLand,
    advance_to_phase,
    assert_in_zone,
    assert_life_total,
    assert_mana_pool,
    assert_power_toughness,
    assert_stack_empty,
    assert_tapped,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Great Hall of the Biblioplex"


def _quick_fix() -> Instant:
    return Instant(name="Quick Fix", mana_cost=ManaCost(generic=1))


def _setup_hall(game):
    """Place the Great Hall on player 0's battlefield in the main phase."""
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    hall = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[hall])
    return hall


def _animate(game, hall) -> None:
    """Pay {5} and resolve the animation ability."""
    set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
    set_player(game, 0, DeterministicPlayer("P0", script=[
        perform_action(ActivateAbility(hall, 2)),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
    priority_loop(game)
    assert_power_toughness(game, hall, 2, 4)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = GreatHallOfTheBiblioplex()
        assert card.name == _NAME
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.mana_cost.cmc == 0
        assert card.mana_cost.pips == {}


class TestLandDrop:
    def test_played_as_the_one_land_per_turn(self) -> None:
        """The Great Hall is played from hand as the turn's land drop; a
        second land play the same turn is illegal."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        set_board_state(game, 0, hand=[GreatHallOfTheBiblioplex(), "Mountain"])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(PlayLand(_NAME)),
            perform_illegal_action(PlayLand("Mountain")),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.BATTLEFIELD, _NAME)
        assert_in_zone(game, 0, Zone.HAND, "Mountain")


class TestManaAbilities:
    def test_first_ability_adds_colorless(self) -> None:
        """{T}: Add {C} — printed ability index 0."""
        game = create_game()
        hall = _setup_hall(game)

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(hall, 0)),
        ]))
        set_player(game, 1, DeterministicPlayer("P1"))
        priority_loop(game)

        assert_mana_pool(game, 0, {ManaType.COLORLESS: 1})
        assert_tapped(game, hall, True)
        assert_life_total(game, 0, 20)

    def test_second_ability_costs_life_and_taps(self) -> None:
        """{T}, Pay 1 life: Add one mana of any color — printed ability index 1.
        The color is the controller's choice; here white is floated."""
        game = create_game()
        hall = _setup_hall(game)

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(hall, 1)),
        ], choices=[ManaType.WHITE]))
        set_player(game, 1, DeterministicPlayer("P1"))
        priority_loop(game)

        assert_life_total(game, 0, 19)
        assert_mana_pool(game, 0, {ManaType.WHITE: 1})
        assert_tapped(game, hall, True)

    def test_restricted_mana_pays_an_instant(self) -> None:
        """Mana from the second ability legally pays for an instant."""
        game = create_game()
        hall = _setup_hall(game)
        set_board_state(game, 0, hand=[_quick_fix()])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(hall, 1)),
            perform_action(CastSpell("Quick Fix")),
            no_op(),
            no_op(),
        ], choices=[ManaType.WHITE]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op(), no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.GRAVEYARD, "Quick Fix")
        assert_mana_pool(game, 0, {})
        assert_life_total(game, 0, 19)

    def test_restricted_mana_rejected_for_a_creature(self) -> None:
        """The same mana cannot be spent on a creature spell."""
        game = create_game()
        hall = _setup_hall(game)
        bear = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            mana_cost=ManaCost(generic=1),
        )
        set_board_state(game, 0, hand=[bear])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(hall, 1)),
            perform_illegal_action(CastSpell("Grizzly Bears")),
            no_op(),
        ], choices=[ManaType.WHITE]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.HAND, "Grizzly Bears")
        assert_mana_pool(game, 0, {ManaType.WHITE: 1})


class TestAnimation:
    def test_animation_makes_a_2_4_wizard_that_is_still_a_land(self) -> None:
        """{5} turns the untapped land into a 2/4 creature; it stays a land."""
        game = create_game()
        hall = _setup_hall(game)
        _animate(game, hall)

        assert_power_toughness(game, hall, 2, 4)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert_mana_pool(game, 0, {})
        assert_stack_empty(game)

    def test_animation_requires_five_mana(self) -> None:
        """With only four mana the activation is illegal and nothing changes."""
        game = create_game()
        hall = _setup_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 4})

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_illegal_action(ActivateAbility(hall, 2)),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        # A non-creature land has no power/toughness to assert; the gate is
        # simply that the illegal activation left it a non-creature.
        assert CardType.CREATURE not in hall.card_types
        assert_mana_pool(game, 0, {ManaType.COLORLESS: 4})

    def test_reanimation_is_a_gated_noop(self) -> None:
        """'If this land isn't a creature' gates the effect: a second
        activation pays its cost but changes nothing."""
        game = create_game()
        hall = _setup_hall(game)
        _animate(game, hall)

        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(hall, 2)),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_power_toughness(game, hall, 2, 4)
        assert_mana_pool(game, 0, {})


class TestSpellCastBoost:
    def test_boost_on_controller_instant_and_reset_at_cleanup(self) -> None:
        """Casting an instant boosts the animated Hall to 3/4 until end of
        turn; the cleanup step resets the boost but not the animation."""
        game = create_game()
        hall = _setup_hall(game)
        _animate(game, hall)

        set_board_state(game, 0, hand=[_quick_fix()], mana={ManaType.COLORLESS: 1})
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell("Quick Fix")),
            no_op(),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op(), no_op()]))
        priority_loop(game)

        assert_power_toughness(game, hall, 3, 4)

        # Until end of turn: the cleanup step removes the boost only.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert_power_toughness(game, hall, 2, 4)
        assert CardType.CREATURE in hall.card_types

    def test_opponent_spell_does_not_boost(self) -> None:
        """Only the controller's instants/sorceries trigger the boost."""
        game = create_game()
        hall = _setup_hall(game)
        _animate(game, hall)

        set_board_state(game, 1, hand=[_quick_fix()], mana={ManaType.COLORLESS: 1})
        set_player(game, 0, DeterministicPlayer("P0", script=[no_op(), no_op()]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpell("Quick Fix")),
            no_op(),
        ]))
        priority_loop(game)

        assert_in_zone(game, 1, Zone.GRAVEYARD, "Quick Fix")
        assert_power_toughness(game, hall, 2, 4)

    def test_two_spells_stack_boosts(self) -> None:
        """Two instants in the same turn give +2/+0 total."""
        game = create_game()
        hall = _setup_hall(game)
        _animate(game, hall)

        set_board_state(
            game, 0,
            hand=[_quick_fix(), _quick_fix()],
            mana={ManaType.COLORLESS: 2},
        )
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell("Quick Fix")),
            no_op(),
            no_op(),
            perform_action(CastSpell("Quick Fix")),
            no_op(),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            no_op(), no_op(), no_op(), no_op(),
        ]))
        priority_loop(game)

        assert_power_toughness(game, hall, 4, 4)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Quick Fix", count=2)

    def test_no_boost_when_not_animated(self) -> None:
        """Without the animation the land has no spell-cast trigger."""
        game = create_game()
        hall = _setup_hall(game)

        set_board_state(game, 0, hand=[_quick_fix()], mana={ManaType.COLORLESS: 1})
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell("Quick Fix")),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.GRAVEYARD, "Quick Fix")
        # No animation → still a non-creature land (no power/toughness to boost).
        assert CardType.CREATURE not in hall.card_types
