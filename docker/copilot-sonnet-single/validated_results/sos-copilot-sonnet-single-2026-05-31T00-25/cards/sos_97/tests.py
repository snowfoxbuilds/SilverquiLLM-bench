"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_ral(game=None):
    """Create a RalZarekGuestLecturer owned by player 0 (or no owner)."""
    if game is None:
        return RalZarekGuestLecturer(owner=None)
    p1 = game.players[0]
    return RalZarekGuestLecturer(owner=p1, controller=p1)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    def test_name(self):
        assert _make_ral().name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self):
        assert _make_ral().mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self):
        assert isinstance(_make_ral(), Planeswalker)

    def test_card_type(self):
        assert CardType.PLANESWALKER in _make_ral().card_types

    def test_legendary_supertype(self):
        assert Supertype.LEGENDARY in _make_ral().supertypes

    def test_ral_subtype(self):
        assert "Ral" in _make_ral().subtypes

    def test_starting_loyalty(self):
        ral = _make_ral()
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3

    def test_color_black(self):
        ral = _make_ral()
        assert ManaType.BLACK in ral.mana_cost.pips

    def test_four_loyalty_abilities(self):
        ral = _make_ral()
        abilities = ral.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_ability_costs(self):
        abilities = _make_ral().get_loyalty_abilities()
        costs = [a.loyalty_cost for a in abilities]
        assert +1 in costs
        assert -1 in costs
        assert -2 in costs
        assert -7 in costs


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------

class TestPlusOneSurveil:
    def test_surveil_moves_top_two_to_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        from engine.card import CardImpl
        card_a = CardImpl(name="Card A", owner=p1, controller=p1)
        card_b = CardImpl(name="Card B", owner=p1, controller=p1)
        card_c = CardImpl(name="Card C", owner=p1, controller=p1)

        set_board_state(game, 0, graveyard=[])
        # Put cards into library: bottom → top = [C, B, A] so A is top
        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        lib.add(card_c)
        lib.add(card_b)
        lib.add(card_a)  # top

        gy = game.get_graveyard(p1)
        assert len(gy) == 0

        ability = ral.get_loyalty_abilities()[0]  # +1
        assert ability.loyalty_cost == +1
        ability.effect(game)

        # Top 2 (A and B) should now be in graveyard
        gy_cards = gy.get_all()
        assert len(gy_cards) == 2
        gy_names = {c.name for c in gy_cards}
        assert "Card A" in gy_names
        assert "Card B" in gy_names
        # Card C should still be in library
        lib_cards = lib.get_all()
        assert len(lib_cards) == 1
        assert lib_cards[0].name == "Card C"

    def test_surveil_with_fewer_than_two_cards(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        from engine.card import CardImpl
        card_a = CardImpl(name="Only Card", owner=p1, controller=p1)

        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        lib.add(card_a)

        gy = game.get_graveyard(p1)
        for obj in gy.get_all():
            gy.remove(obj)

        ability = ral.get_loyalty_abilities()[0]
        ability.effect(game)

        # The single card should have moved to graveyard
        assert len(gy) == 1

    def test_surveil_empty_library_does_not_raise(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)

        ability = ral.get_loyalty_abilities()[0]
        # Should not raise
        ability.effect(game)


# ---------------------------------------------------------------------------
# -1: Any number of target players each discard a card
# ---------------------------------------------------------------------------

class TestMinusOneDiscard:
    def test_target_player_discards_a_card(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = _make_ral(game)

        from engine.card import CardImpl
        card = CardImpl(name="Discard Me", owner=p2, controller=p2)

        set_board_state(game, 1, hand=[card])

        # Script p2 to choose the card when asked to discard
        from engine.player import DeterministicPlayer
        p2._script.appendleft(card)

        # Set targets on the planeswalker
        ral._resolve_targets = [p2]

        ability = ral.get_loyalty_abilities()[1]  # -1
        assert ability.loyalty_cost == -1
        ability.effect(game)

        # Card should now be in graveyard
        assert game.get_graveyard(p2).contains(card)
        assert not game.get_hand(p2).contains(card)

    def test_multiple_targets_each_discard(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = _make_ral(game)

        from engine.card import CardImpl
        card1 = CardImpl(name="Card1", owner=p1, controller=p1)
        card2 = CardImpl(name="Card2", owner=p2, controller=p2)

        set_board_state(game, 0, hand=[card1])
        set_board_state(game, 1, hand=[card2])

        p1._script.appendleft(card1)
        p2._script.appendleft(card2)

        ral._resolve_targets = [p1, p2]

        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)

        assert game.get_graveyard(p1).contains(card1)
        assert game.get_graveyard(p2).contains(card2)

    def test_no_targets_is_noop(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        ral._resolve_targets = []

        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)  # Should not raise

    def test_target_with_empty_hand_skipped(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        set_board_state(game, 0, hand=[])

        ral._resolve_targets = [p1]

        ability = ral.get_loyalty_abilities()[1]
        ability.effect(game)  # Should not raise


# ---------------------------------------------------------------------------
# -2: Return creature from graveyard to battlefield
# ---------------------------------------------------------------------------

class TestMinusTwoRecursion:
    def test_returns_creature_from_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        creature = Creature(
            name="Small Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
            mana_cost=ManaCost.parse("{2}"),
        )

        set_board_state(game, 0, graveyard=[creature])

        ral._resolve_target = creature

        ability = ral.get_loyalty_abilities()[2]  # -2
        assert ability.loyalty_cost == -2
        ability.effect(game)

        bf = game.get_battlefield(p1)
        assert bf.contains(creature)
        assert not game.get_graveyard(p1).contains(creature)

    def test_creature_controller_is_set(self):
        game = create_game()
        p1 = game.players[0]
        ral = _make_ral(game)

        creature = Creature(
            name="Undead",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
            mana_cost=ManaCost.parse("{1}"),
        )

        set_board_state(game, 0, graveyard=[creature])

        ral._resolve_target = creature
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)

        assert creature.controller is p1

    def test_no_target_is_noop(self):
        game = create_game()
        ral = _make_ral(game)

        ral._resolve_target = None
        ability = ral.get_loyalty_abilities()[2]
        ability.effect(game)  # Should not raise


# ---------------------------------------------------------------------------
# -7: Flip five coins, opponent skips turns equal to heads
# ---------------------------------------------------------------------------

class TestMinusSevenCoinFlip:
    def test_all_heads_opponent_skips_five_turns(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = _make_ral(game)

        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]  # -7
        assert ability.loyalty_cost == -7

        # All coins come up heads
        with patch("cards.sos.sos_97.card_impl.random.random", return_value=0.1):
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 5

    def test_all_tails_opponent_skips_zero_turns(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = _make_ral(game)

        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]

        # All coins come up tails (random() >= 0.5)
        with patch("cards.sos.sos_97.card_impl.random.random", return_value=0.9):
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 0

    def test_three_heads_opponent_skips_three_turns(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = _make_ral(game)

        ral._resolve_target = p2

        ability = ral.get_loyalty_abilities()[3]

        # 3 heads, 2 tails via side_effect
        flip_results = [0.1, 0.1, 0.1, 0.9, 0.9]
        with patch("cards.sos.sos_97.card_impl.random.random", side_effect=flip_results):
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 3

    def test_skip_turns_accumulates(self):
        """If the ability fires twice, turns_to_skip stacks."""
        game = create_game()
        p2 = game.players[1]
        ral = _make_ral(game)

        ral._resolve_target = p2
        ability = ral.get_loyalty_abilities()[3]

        with patch("cards.sos.sos_97.card_impl.random.random", return_value=0.1):
            ability.effect(game)  # heads = 5
            ral._resolve_target = p2
            ability.effect(game)  # heads = 5 more

        assert getattr(p2, "turns_to_skip", 0) == 10

    def test_no_target_does_not_raise(self):
        game = create_game()
        ral = _make_ral(game)

        ral._resolve_target = None
        ability = ral.get_loyalty_abilities()[3]

        with patch("cards.sos.sos_97.card_impl.random.random", return_value=0.1):
            ability.effect(game)  # Should not raise


# ---------------------------------------------------------------------------
# Loyalty cost verification (integration-level: adjust and check)
# ---------------------------------------------------------------------------

class TestLoyaltyCosts:
    def test_loyalty_costs_match_spec(self):
        ral = _make_ral()
        abilities = ral.get_loyalty_abilities()
        cost_map = {a.loyalty_cost for a in abilities}
        assert cost_map == {+1, -1, -2, -7}
