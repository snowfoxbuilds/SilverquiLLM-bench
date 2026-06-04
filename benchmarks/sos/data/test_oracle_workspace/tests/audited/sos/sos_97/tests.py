"""Audited tests for Ral Zarek, Guest Lecturer (sos_97).

Oracle: {1}{B}{B} Legendary Planeswalker — Ral, loyalty 3.
  +1: Surveil 2.
  −1: Any number of target players each discard a card.
  −2: Return target creature card with mana value 3 or less from your
      graveyard to the battlefield.
  −7: Flip five coins.  Target opponent skips their next X turns, where X is
      the number of coins that came up heads.

Simulation-only shape (AUDITED-TEST-API.md): loyalty abilities are activated
by printed-order index via ``ActivateAbility`` directives inside
``priority_loop`` (sorcery speed → the tests first ``advance_to_phase`` into
the main phase).  Randomness is controlled by seed-replacement:
``create_game(seed=...)`` seeds ``game.rng`` and the expected value is
re-derived from an identically-seeded ``random.Random``.  Exception-signalled
illegality (insufficient loyalty, the once-per-turn re-activation) is
asserted with ``perform_illegal_action``.

Tests:
  1. test_card_identity
  2. test_plus_one_surveil_both_to_graveyard
  3. test_plus_one_surveil_keep_one_on_top
  4. test_minus_one_targeted_player_discards
  5. test_minus_two_returns_creature_from_graveyard
  6. test_ultimate_skips_turns_per_seeded_coin_flips
  7. test_insufficient_loyalty_rejected
  8. test_planeswalker_dies_at_zero_loyalty
  9. test_second_loyalty_activation_same_turn_rejected
"""

from __future__ import annotations

import random

from card_impl import RalZarekGuestLecturer

from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    ActivateAbility,
    DeterministicPlayer,
    PermanentSpec,
    advance_to_phase,
    assert_counters,
    assert_in_zone,
    assert_library_order,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Ral Zarek, Guest Lecturer"


def _setup(game, *, loyalty: int = 3):
    """Place Ral on player 0's battlefield in the main phase; return him."""
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    ral = RalZarekGuestLecturer()
    set_board_state(
        game, 0, battlefield=[PermanentSpec(ral, counters={"loyalty": loyalty})],
    )
    return ral


def _activate(game, directive, *, p0_choices=(), p1_choices=()) -> None:
    """Run one loyalty activation (plus a resolution round) to completion."""
    set_player(game, 0, DeterministicPlayer("P0", script=[
        directive,
        no_op(),
        no_op(),
    ], choices=list(p0_choices)))
    set_player(game, 1, DeterministicPlayer("P1", script=[
        no_op(),
        no_op(),
    ], choices=list(p1_choices)))
    priority_loop(game)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = RalZarekGuestLecturer()
        assert card.name == _NAME
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.BLACK) == 2
        assert card.mana_cost.cmc == 3
        assert CardType.PLANESWALKER in card.card_types
        assert isinstance(card, Planeswalker)
        assert "Ral" in card.subtypes
        assert card.starting_loyalty == 3


class TestPlusOne:
    def test_plus_one_surveil_both_to_graveyard(self) -> None:
        """+1: Surveil 2 — both surveiled cards may go to the graveyard;
        loyalty goes from 3 to 4."""
        game = create_game()
        ral = _setup(game)

        card_a = Creature(name="CardA", base_power=1, base_toughness=1)
        card_b = Creature(name="CardB", base_power=1, base_toughness=1)
        set_board_state(game, 0, library=[card_a, card_b])

        _activate(
            game,
            perform_action(ActivateAbility(ral, 0)),
            p0_choices=[card_a, card_b],
        )

        assert_counters(game, ral, {"loyalty": 4})
        assert_in_zone(game, 0, Zone.GRAVEYARD, "CardA")
        assert_in_zone(game, 0, Zone.GRAVEYARD, "CardB")
        assert_zone_count(game, 0, Zone.LIBRARY, 0)

    def test_plus_one_surveil_keep_one_on_top(self) -> None:
        """+1: Surveil 2 — declining the second pick keeps that card on top."""
        game = create_game()
        ral = _setup(game)

        card_a = Creature(name="CardA", base_power=1, base_toughness=1)
        card_b = Creature(name="CardB", base_power=1, base_toughness=1)
        set_board_state(game, 0, library=[card_a, card_b])

        _activate(
            game,
            perform_action(ActivateAbility(ral, 0)),
            p0_choices=[card_a, None],
        )

        assert_counters(game, ral, {"loyalty": 4})
        assert_in_zone(game, 0, Zone.GRAVEYARD, "CardA")
        assert_library_order(game, 0, ["CardB"])


class TestMinusOne:
    def test_minus_one_targeted_player_discards(self) -> None:
        """−1: the targeted player discards a card of their choice."""
        game = create_game()
        ral = _setup(game)

        victim = Creature(name="VictimCard", base_power=2, base_toughness=2)
        set_board_state(game, 1, hand=[victim])

        _activate(
            game,
            perform_action(ActivateAbility(ral, 1, targets=[game.players[1]])),
            p1_choices=[victim],
        )

        assert_counters(game, ral, {"loyalty": 2})
        assert_in_zone(game, 1, Zone.GRAVEYARD, "VictimCard")
        assert_zone_count(game, 1, Zone.HAND, 0)


class TestMinusTwo:
    def test_minus_two_returns_creature_from_graveyard(self) -> None:
        """−2: a creature card with mana value ≤ 3 returns from the graveyard
        to the battlefield."""
        game = create_game()
        ral = _setup(game)

        zombie = Creature(
            name="Zombie",
            base_power=2,
            base_toughness=2,
            mana_cost=ManaCost(generic=1, pips={ManaType.BLACK: 1}),  # CMC 2
        )
        set_board_state(game, 0, graveyard=[zombie])

        _activate(
            game,
            perform_action(ActivateAbility(ral, 2, targets=[zombie])),
        )

        assert_counters(game, ral, {"loyalty": 1})
        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Zombie")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)


class TestUltimate:
    def test_ultimate_skips_turns_per_seeded_coin_flips(self) -> None:
        """−7: with a seeded RNG, the opponent is set to skip exactly as many
        turns as an identically-seeded RNG produces heads in five flips.

        The engine has no turn-skip machinery yet (multi-player turn control
        is deferred), so the recorded skip count on the targeted opponent is
        the observable outcome of this ability.
        """
        seed = 1337
        game = create_game(seed=seed)
        ral = _setup(game, loyalty=10)

        reference_rng = random.Random(seed)
        expected_heads = sum(reference_rng.randint(0, 1) for _ in range(5))

        _activate(
            game,
            perform_action(ActivateAbility(ral, 3, targets=[game.players[1]])),
        )

        assert_counters(game, ral, {"loyalty": 3})
        assert getattr(game.players[1], "skip_turns", 0) == expected_heads


class TestLoyaltyLegality:
    def test_insufficient_loyalty_rejected(self) -> None:
        """−2 with only 1 loyalty is illegal; loyalty is unchanged."""
        game = create_game()
        ral = _setup(game, loyalty=1)

        zombie = Creature(
            name="Zombie",
            base_power=2,
            base_toughness=2,
            mana_cost=ManaCost(generic=1, pips={ManaType.BLACK: 1}),
        )
        set_board_state(game, 0, graveyard=[zombie])

        _activate(
            game,
            perform_illegal_action(ActivateAbility(ral, 2, targets=[zombie])),
        )

        assert_counters(game, ral, {"loyalty": 1})
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Zombie")

    def test_planeswalker_dies_at_zero_loyalty(self) -> None:
        """Activating −1 at 1 loyalty leaves 0 — state-based actions put the
        planeswalker into its owner's graveyard."""
        game = create_game()
        ral = _setup(game, loyalty=1)

        # Opponent's hand is empty, so the −1 resolves with no discard.
        _activate(
            game,
            perform_action(ActivateAbility(ral, 1, targets=[game.players[1]])),
        )

        assert_in_zone(game, 0, Zone.GRAVEYARD, _NAME)
        assert_zone_count(game, 0, Zone.BATTLEFIELD, 0)

    def test_second_loyalty_activation_same_turn_rejected(self) -> None:
        """Loyalty abilities are once per turn: the second activation is
        exception-signalled illegal and changes nothing."""
        game = create_game()
        ral = _setup(game, loyalty=5)
        # Empty library → the +1 surveil resolves without choices.

        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(ActivateAbility(ral, 0)),
            no_op(),
            perform_illegal_action(ActivateAbility(ral, 1, targets=[game.players[1]])),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            no_op(),
            no_op(),
        ]))
        priority_loop(game)

        # +1 applied; the rejected −1 did not.
        assert_counters(game, ral, {"loyalty": 6})
