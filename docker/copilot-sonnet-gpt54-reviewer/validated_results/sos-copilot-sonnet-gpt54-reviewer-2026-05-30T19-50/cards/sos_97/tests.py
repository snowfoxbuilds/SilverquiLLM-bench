"""Tests for Ral Zarek, Guest Lecturer (sos_97).

Covers:
- Static card properties (name, type, subtype, loyalty=3)
- +1 ability: Surveil 2 (look at top 2, put some to graveyard, rest stay on top)
- -1 ability: target players discard a card
- -2 ability: return creature with MV ≤ 3 from graveyard to battlefield
- -2 ability: does NOT return creature with MV > 3
- -7 ability: flip coins, opponent skips turns based on heads
- Loyalty counter adjustments
"""

from __future__ import annotations

import random
from typing import Any
from unittest.mock import patch

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    """Static card data must match the sos_97 spec."""

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        costs = [a.loyalty_cost for a in abilities]
        assert +1 in costs
        assert -1 in costs
        assert -2 in costs
        assert -7 in costs

    def test_all_abilities_are_loyalty_ability(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        for ability in card.get_loyalty_abilities():
            assert isinstance(ability, LoyaltyAbility)


# ---------------------------------------------------------------------------
# +1 ability: Surveil 2
# ---------------------------------------------------------------------------

class TestPlusOneSurveil:
    """Surveil 2 — look at top 2 cards; put any into graveyard, rest on top."""

    def _get_plus1(self, card: RalZarekGuestLecturer) -> LoyaltyAbility:
        return next(a for a in card.get_loyalty_abilities() if a.loyalty_cost == +1)

    def test_plus1_loyalty_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        ability = self._get_plus1(card)
        assert ability.loyalty_cost == +1

    def test_surveil_puts_card_to_graveyard(self) -> None:
        """When player chooses to send a card to graveyard, it moves there."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Create two library cards.
        card_a = Creature(name="Card A", base_power=1, base_toughness=1)
        card_b = Creature(name="Card B", base_power=2, base_toughness=2)
        card_a.owner = p1
        card_b.owner = p1
        set_board_state(game, 0, hand=[])
        lib = p1.zones[Zone.LIBRARY]
        lib.add(card_a)
        lib.add(card_b)  # card_b is on top

        # Player chooses to put card_b into graveyard.
        original_choose_card = p1.choose_card
        def _mock_choose_cards(cards: Any, desc: str) -> list[Any]:
            # Send the first top card to graveyard.
            return [cards[-1]] if cards else []
        p1.choose_cards = _mock_choose_cards

        ability = self._get_plus1(ral)
        ability.effect(game)

        gy = p1.zones[Zone.GRAVEYARD]
        assert gy.contains(card_b), "Chosen card should be in graveyard after surveil"

    def test_surveil_keeps_card_on_top_of_library(self) -> None:
        """Card not chosen for graveyard stays in library."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        card_a = Creature(name="Card A", base_power=1, base_toughness=1)
        card_a.owner = p1
        set_board_state(game, 0, hand=[])
        lib = p1.zones[Zone.LIBRARY]
        lib.add(card_a)

        # Player keeps card (no cards chosen to graveyard).
        p1.choose_cards = lambda cards, desc: []

        ability = self._get_plus1(ral)
        ability.effect(game)

        assert lib.contains(card_a), "Kept card should remain in library"
        gy = p1.zones[Zone.GRAVEYARD]
        assert not gy.contains(card_a), "Kept card should NOT be in graveyard"

    def test_surveil_empty_library_no_crash(self) -> None:
        """Surveil with empty library should not raise."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[])

        ability = self._get_plus1(ral)
        # Should not raise even with empty library.
        ability.effect(game)

    def test_surveil_looks_at_at_most_two_cards(self) -> None:
        """Surveil looks at top 2 cards (even if library has more)."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[])
        lib = p1.zones[Zone.LIBRARY]

        cards_seen = []

        def _mock_choose_cards(cards: Any, desc: str) -> list[Any]:
            cards_seen.extend(cards)
            return []

        for i in range(5):
            c = Creature(name=f"Card {i}", base_power=1, base_toughness=1)
            c.owner = p1
            lib.add(c)

        p1.choose_cards = _mock_choose_cards
        ability = self._get_plus1(ral)
        ability.effect(game)

        assert len(cards_seen) == 2, "Surveil should look at exactly 2 cards"


# ---------------------------------------------------------------------------
# -1 ability: Any number of target players discard a card
# ---------------------------------------------------------------------------

class TestMinusOneDiscard:
    """−1: Any number of target players each discard a card."""

    def _get_minus1(self, card: RalZarekGuestLecturer) -> LoyaltyAbility:
        return next(a for a in card.get_loyalty_abilities() if a.loyalty_cost == -1)

    def test_minus1_loyalty_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        ability = self._get_minus1(card)
        assert ability.loyalty_cost == -1

    def test_target_player_discards_card(self) -> None:
        """Targeted player discards a card from hand."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        hand_card = Creature(name="Hand Card", base_power=2, base_toughness=2)
        hand_card.owner = p2
        set_board_state(game, 1, hand=[hand_card])

        # Target p2.
        ral.chosen_targets = [p2]

        ability = self._get_minus1(ral)
        ability.effect(game)

        hand = p2.zones[Zone.HAND]
        gy = p2.zones[Zone.GRAVEYARD]
        assert not hand.contains(hand_card), "Discarded card should leave hand"
        assert gy.contains(hand_card), "Discarded card should be in graveyard"

    def test_multiple_targets_each_discard(self) -> None:
        """Each targeted player discards a card."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        c1 = Creature(name="P1 Card", base_power=1, base_toughness=1)
        c2 = Creature(name="P2 Card", base_power=1, base_toughness=1)
        c1.owner = p1
        c2.owner = p2
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])

        ral.chosen_targets = [p1, p2]

        ability = self._get_minus1(ral)
        ability.effect(game)

        gy1 = p1.zones[Zone.GRAVEYARD]
        gy2 = p2.zones[Zone.GRAVEYARD]
        assert gy1.contains(c1), "P1's card should be in graveyard"
        assert gy2.contains(c2), "P2's card should be in graveyard"

    def test_no_targets_no_discard(self) -> None:
        """With no targets, nobody discards."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        c1 = Creature(name="Hand Card", base_power=1, base_toughness=1)
        c1.owner = p1
        set_board_state(game, 0, hand=[c1])
        ral.chosen_targets = []

        ability = self._get_minus1(ral)
        ability.effect(game)

        hand = p1.zones[Zone.HAND]
        assert hand.contains(c1), "Card should remain in hand when no targets chosen"

    def test_empty_hand_no_crash(self) -> None:
        """Targeting a player with empty hand should not raise."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 1, hand=[])
        ral.chosen_targets = [p2]

        ability = self._get_minus1(ral)
        ability.effect(game)  # Should not raise.


# ---------------------------------------------------------------------------
# -2 ability: Return creature with MV ≤ 3 from graveyard to battlefield
# ---------------------------------------------------------------------------

class TestMinusTwoReanimation:
    """−2: Return target creature card with mana value ≤ 3 from your graveyard."""

    def _get_minus2(self, card: RalZarekGuestLecturer) -> LoyaltyAbility:
        return next(a for a in card.get_loyalty_abilities() if a.loyalty_cost == -2)

    def test_minus2_loyalty_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        ability = self._get_minus2(card)
        assert ability.loyalty_cost == -2

    def _make_creature(self, name: str, mana_cost_str: str, owner: Any) -> Creature:
        c = Creature(name=name, base_power=2, base_toughness=2)
        c.mana_cost = ManaCost.parse(mana_cost_str)
        c.owner = owner
        c.controller = owner
        return c

    def test_returns_creature_with_mv_lte_3(self) -> None:
        """Creature with MV 3 returns to battlefield from graveyard."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = self._make_creature("Zombie", "{1}{B}{B}", p1)  # MV=3
        set_board_state(game, 0, graveyard=[creature])

        ral._resolve_target = creature
        ability = self._get_minus2(ral)
        ability.effect(game)

        bf = p1.zones[Zone.BATTLEFIELD]
        gy = p1.zones[Zone.GRAVEYARD]
        assert bf.contains(creature), "Creature should be on battlefield after reanimation"
        assert not gy.contains(creature), "Creature should not remain in graveyard"

    def test_returns_creature_with_mv_1(self) -> None:
        """Creature with MV 1 can be reanimated."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = self._make_creature("Rat", "{B}", p1)  # MV=1
        set_board_state(game, 0, graveyard=[creature])

        ral._resolve_target = creature
        ability = self._get_minus2(ral)
        ability.effect(game)

        bf = p1.zones[Zone.BATTLEFIELD]
        assert bf.contains(creature)

    def test_does_not_return_creature_with_mv_4(self) -> None:
        """Creature with MV 4 cannot be reanimated."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = self._make_creature("Dragon", "{2}{B}{B}", p1)  # MV=4
        set_board_state(game, 0, graveyard=[creature])

        ral._resolve_target = creature
        ability = self._get_minus2(ral)
        ability.effect(game)

        bf = p1.zones[Zone.BATTLEFIELD]
        gy = p1.zones[Zone.GRAVEYARD]
        assert not bf.contains(creature), "Creature with MV 4 should NOT be reanimated"
        assert gy.contains(creature), "Creature with MV 4 should remain in graveyard"

    def test_does_not_return_creature_not_in_graveyard(self) -> None:
        """Target not in controller's graveyard does nothing."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        creature = self._make_creature("Zombie", "{B}", p1)
        # Put it in hand, not graveyard.
        set_board_state(game, 0, hand=[creature])

        ral._resolve_target = creature
        ability = self._get_minus2(ral)
        ability.effect(game)

        bf = p1.zones[Zone.BATTLEFIELD]
        assert not bf.contains(creature), "Creature not in graveyard should not be reanimated"

    def test_no_target_no_crash(self) -> None:
        """With no target set, ability does nothing."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ability = self._get_minus2(ral)
        ability.effect(game)  # Should not raise.


# ---------------------------------------------------------------------------
# -7 ability: Flip five coins, opponent skips turns
# ---------------------------------------------------------------------------

class TestMinusSevenCoinFlip:
    """−7: Flip 5 coins; target opponent skips next X turns (X = heads)."""

    def _get_minus7(self, card: RalZarekGuestLecturer) -> LoyaltyAbility:
        return next(a for a in card.get_loyalty_abilities() if a.loyalty_cost == -7)

    def test_minus7_loyalty_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        ability = self._get_minus7(card)
        assert ability.loyalty_cost == -7

    def test_all_heads_skips_five_turns(self) -> None:
        """Five heads → opponent skips 5 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2

        # Force all flips to heads (1).
        with patch("random.randint", return_value=1):
            ability = self._get_minus7(ral)
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 5

    def test_all_tails_skips_zero_turns(self) -> None:
        """Zero heads → opponent skips 0 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2

        with patch("random.randint", return_value=0):
            ability = self._get_minus7(ral)
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 0

    def test_three_heads_skips_three_turns(self) -> None:
        """Three heads → opponent skips 3 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2

        flip_sequence = iter([1, 0, 1, 0, 1])  # 3 heads
        with patch("random.randint", side_effect=flip_sequence):
            ability = self._get_minus7(ral)
            ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 3

    def test_skips_accumulate_from_multiple_activations(self) -> None:
        """Multiple activations accumulate skips on opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Force 2 heads each time.
        flip_sequence = [1, 1, 0, 0, 0, 1, 1, 0, 0, 0]
        with patch("random.randint", side_effect=iter(flip_sequence)):
            for _ in range(2):
                ral = RalZarekGuestLecturer(owner=p1, controller=p1)
                ral._resolve_target = p2
                ability = self._get_minus7(ral)
                ability.effect(game)

        assert getattr(p2, "turns_to_skip", 0) == 4

    def test_no_target_no_crash(self) -> None:
        """With no target, ability does nothing."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        with patch("random.randint", return_value=1):
            ability = self._get_minus7(ral)
            ability.effect(game)  # Should not raise.


# ---------------------------------------------------------------------------
# Turn-skipping integration
# ---------------------------------------------------------------------------

class TestTurnSkipping:
    """Verify that turns_to_skip causes the engine to skip turns."""

    def test_opponent_turn_skipped_when_turns_to_skip_set(self) -> None:
        """After setting turns_to_skip=1 on p2, p2's next turn is skipped."""
        game = create_game()
        p2 = game.players[1]

        # Ensure we're at the start of p1's turn.
        assert game.active_player_index == 0

        # Set p2 to skip 1 turn.
        p2.turns_to_skip = 1

        # Advance through a full turn to trigger turn rotation.
        from engine.types import Phase, Step
        # Advance to end of p1's turn.
        while not (game.phase == Phase.ENDING and game.step == Step.CLEANUP):
            game.advance_phase()

        # Now advance to the end of cleanup — triggers turn change.
        game.advance_phase()

        # p2 should have been skipped; p1 should be active again.
        assert game.active_player_index == 0, (
            "p1 should be active because p2's turn was skipped"
        )
        assert p2.turns_to_skip == 0, "turns_to_skip should be decremented"

    def test_loyalty_adjustment_plus1(self) -> None:
        """Starting at 3 loyalty, +1 gives 4 loyalty."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        assert ral.loyalty == 3

        # Manually apply loyalty cost as abilities do.
        ral.loyalty += 1
        assert ral.loyalty == 4

    def test_loyalty_adjustment_minus2(self) -> None:
        """Starting at 3 loyalty, −2 gives 1 loyalty."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty -= 2
        assert ral.loyalty == 1
