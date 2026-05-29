"""Tests for sos_97 — Ral Zarek, Guest Lecturer.

TDD red-phase tests.  All tests are expected to FAIL until the implementation
in card_impl.py is complete.

Coverage:
- Static properties (name, mana cost, type, loyalty, legendary, subtype "Ral")
- get_loyalty_abilities() returns 4 abilities with correct loyalty costs
- [+1] Surveil 2: top cards move to graveyard or stay based on controller choice
- [−1] Any number of target players each discard a card
- [−2] Return target creature with MV ≤ 3 from controller's own graveyard to BF
- [−7] Flip 5 coins; opponent skips their next X turns (X = heads)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ability_by_cost(card: RalZarekGuestLecturer, cost: int):
    """Return the LoyaltyAbility with the given loyalty_cost, or raise."""
    for ability in card.get_loyalty_abilities():
        if ability.loyalty_cost == cost:
            return ability
    raise AssertionError(
        f"No loyalty ability with cost {cost} found on {card.name}"
    )


def _creature(name: str, mv: int = 2, owner=None) -> Creature:
    """Create a vanilla creature with a specific mana value."""
    cost_str = "{" + str(mv) + "}" if mv > 0 else "{0}"
    c = Creature(
        name=name,
        mana_cost=ManaCost.parse(cost_str),
        owner=owner,
        base_power=2,
        base_toughness=2,
    )
    return c


def _clear_library(game, player_index: int) -> None:
    """Remove all cards from the given player's library."""
    p = game.players[player_index]
    for c in list(p.zones[Zone.LIBRARY].get_all()):
        p.zones[Zone.LIBRARY].remove(c)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    """Static card data should match the card spec."""

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker_subclass(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_has_planeswalker_card_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_is_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_starting_loyalty_is_3(self) -> None:
        assert RalZarekGuestLecturer(owner=None).starting_loyalty == 3

    def test_current_loyalty_starts_at_3(self) -> None:
        assert RalZarekGuestLecturer(owner=None).loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability declarations
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyAbilities:
    """get_loyalty_abilities() declares 4 abilities with correct costs."""

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert len(card.get_loyalty_abilities()) == 4

    def test_plus1_loyalty_cost_present(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert 1 in costs, f"Expected +1 cost in {costs}"

    def test_minus1_loyalty_cost_present(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert -1 in costs, f"Expected -1 cost in {costs}"

    def test_minus2_loyalty_cost_present(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert -2 in costs, f"Expected -2 cost in {costs}"

    def test_minus7_loyalty_cost_present(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert -7 in costs, f"Expected -7 cost in {costs}"


# ---------------------------------------------------------------------------
# [+1] Surveil 2
# ---------------------------------------------------------------------------

class TestRalZarekPlusOneSurveil:
    """+1 ability: Surveil 2 — look at top 2, put any into graveyard, rest on top."""

    def test_both_top_cards_go_to_graveyard_when_player_says_yes_twice(self) -> None:
        """Controller answers yes twice → both surveiled cards land in graveyard."""
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        _clear_library(game, 0)

        # Add 3 cards to the library so there are 2 to surveil plus one leftover
        lib_cards = [_creature(f"LibCard{i}", owner=p1) for i in range(3)]
        for c in lib_cards:
            p1.zones[Zone.LIBRARY].add(c)

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _ability_by_cost(ral, 1).effect(game)

        gy = list(game.get_graveyard(p1).get_all())
        assert len(gy) == 2

    def test_no_cards_go_to_graveyard_when_player_says_no_twice(self) -> None:
        """Controller answers no twice → both surveiled cards remain on top."""
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        _clear_library(game, 0)

        lib_cards = [_creature(f"KeepCard{i}", owner=p1) for i in range(3)]
        for c in lib_cards:
            p1.zones[Zone.LIBRARY].add(c)

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _ability_by_cost(ral, 1).effect(game)

        gy = list(game.get_graveyard(p1).get_all())
        assert len(gy) == 0
        # Library still has all 3 cards
        lib_remaining = list(p1.zones[Zone.LIBRARY].get_all())
        assert len(lib_remaining) == 3

    def test_surveil_on_empty_library_does_not_raise(self) -> None:
        """Surveil with an empty library is a no-op and must not raise."""
        game = create_game()
        p1 = game.players[0]
        _clear_library(game, 0)

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Should not raise any exception
        _ability_by_cost(ral, 1).effect(game)

    def test_surveil_with_one_card_processes_exactly_one_card(self) -> None:
        """Library with 1 card: only that card is surveiled (sent to GY if yes)."""
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        _clear_library(game, 0)

        lone = _creature("Lone Card", owner=p1)
        p1.zones[Zone.LIBRARY].add(lone)

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _ability_by_cost(ral, 1).effect(game)

        gy = list(game.get_graveyard(p1).get_all())
        assert len(gy) == 1
        assert gy[0] is lone


# ---------------------------------------------------------------------------
# [−1] Any number of target players each discard a card
# ---------------------------------------------------------------------------

class TestRalZarekMinusOneDiscard:
    """−1 ability: each target player discards one card."""

    def test_single_targeted_player_discards_one_card(self) -> None:
        """One targeted player with a single-card hand discards that card."""
        hand_card = _creature("Target Card")
        game = create_game(scripts=([], [hand_card]))
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 1, hand=[hand_card])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p2]
        _ability_by_cost(ral, -1).effect(game)

        gy2 = list(game.get_graveyard(p2).get_all())
        assert len(gy2) == 1

    def test_multiple_targeted_players_each_discard_one_card(self) -> None:
        """Both players targeted → each discards exactly one card."""
        card_p1 = _creature("P1 Card")
        card_p2 = _creature("P2 Card")
        game = create_game(scripts=([card_p1], [card_p2]))
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 0, hand=[card_p1])
        set_board_state(game, 1, hand=[card_p2])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p1, p2]
        _ability_by_cost(ral, -1).effect(game)

        assert len(list(game.get_graveyard(p1).get_all())) == 1
        assert len(list(game.get_graveyard(p2).get_all())) == 1

    def test_no_targets_means_no_cards_discarded(self) -> None:
        """Zero targets chosen → no cards are discarded from any hand."""
        hand_card = _creature("Safe Card")
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 1, hand=[hand_card])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = []
        _ability_by_cost(ral, -1).effect(game)

        gy2 = list(game.get_graveyard(p2).get_all())
        assert len(gy2) == 0


# ---------------------------------------------------------------------------
# [−2] Return target creature (MV ≤ 3) from YOUR graveyard to battlefield
# ---------------------------------------------------------------------------

class TestRalZarekMinusTwoReanimate:
    """−2 ability: reanimate a creature card (MV ≤ 3) from controller's graveyard."""

    def test_mv3_creature_moves_from_own_graveyard_to_battlefield(self) -> None:
        """A MV=3 creature is moved from graveyard to controller's battlefield."""
        game = create_game()
        p1 = game.players[0]

        target = _creature("Three Drop", mv=3, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [target]
        _ability_by_cost(ral, -2).effect(game)

        bf_names = [c.name for c in game.get_battlefield(p1).get_all()]
        assert "Three Drop" in bf_names

    def test_mv3_creature_is_removed_from_graveyard_after_reanimate(self) -> None:
        """After reanimation the creature is no longer in the graveyard."""
        game = create_game()
        p1 = game.players[0]

        target = _creature("Reanimated Creature", mv=3, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [target]
        _ability_by_cost(ral, -2).effect(game)

        gy_names = [c.name for c in game.get_graveyard(p1).get_all()]
        assert "Reanimated Creature" not in gy_names

    def test_mv1_creature_within_range_is_reanimated(self) -> None:
        """MV=1 is well within the ≤3 cap; creature enters battlefield."""
        game = create_game()
        p1 = game.players[0]

        target = _creature("Tiny Creature", mv=1, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [target]
        _ability_by_cost(ral, -2).effect(game)

        bf_names = [c.name for c in game.get_battlefield(p1).get_all()]
        assert "Tiny Creature" in bf_names

    def test_creature_in_opponents_graveyard_is_not_reanimated_to_own_battlefield(
        self,
    ) -> None:
        """A creature from the opponent's graveyard must not enter p1's battlefield.

        The −2 specifies YOUR graveyard; the implementation should only reanimate
        cards that are in the controller's graveyard.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opponent_creature = _creature("Opponent Creature", mv=2, owner=p2)
        set_board_state(game, 1, graveyard=[opponent_creature])

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [opponent_creature]
        _ability_by_cost(ral, -2).effect(game)

        # Should NOT appear on p1's battlefield
        bf1_names = [c.name for c in game.get_battlefield(p1).get_all()]
        assert "Opponent Creature" not in bf1_names


# ---------------------------------------------------------------------------
# [−7] Flip 5 coins; target opponent skips next X turns (X = heads)
# ---------------------------------------------------------------------------

class TestRalZarekMinusSevenCoinFlip:
    """−7 ability: flip 5 coins; target opponent skips X turns (X = heads)."""

    def _run_minus7(self, game, ral, p2, flip_results: list):
        """Helper: run the −7 effect with controlled random outcomes.

        Patches both random.randint and random.random so the implementation
        can use either convention (0/1 ints or 0.0/1.0 floats) for coin flips.
        Heads = 1 (randint) or < 0.5 (random).
        """
        ral.chosen_targets = [p2]
        effect = _ability_by_cost(ral, -7).effect

        # Support either random.randint(0,1) [1=heads] or random.random() [<0.5=heads]
        int_results = [1 if v else 0 for v in flip_results]
        float_results = [0.1 if v else 0.9 for v in flip_results]

        with patch("random.randint", side_effect=int_results), \
             patch("random.random", side_effect=float_results):
            effect(game)

    def test_all_heads_opponent_marked_to_skip_5_turns(self) -> None:
        """All 5 coins heads → opponent's skip-turn counter is set to 5."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        self._run_minus7(game, ral, p2, [True, True, True, True, True])

        skip = getattr(p2, "turns_to_skip", 0)
        assert skip == 5

    def test_all_tails_opponent_skips_0_turns(self) -> None:
        """All 5 coins tails → opponent's skip-turn counter is 0."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        self._run_minus7(game, ral, p2, [False, False, False, False, False])

        skip = getattr(p2, "turns_to_skip", 0)
        assert skip == 0

    def test_three_heads_two_tails_opponent_skips_3_turns(self) -> None:
        """3 heads, 2 tails → opponent skips 3 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        # heads, tails, heads, tails, heads → 3 heads
        self._run_minus7(game, ral, p2, [True, False, True, False, True])

        skip = getattr(p2, "turns_to_skip", 0)
        assert skip == 3
