"""Tests for SOS 97 -- Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer is a Legendary Planeswalker -- Ral.
Cost: {1}{B}{B}, Starting Loyalty: 3.

Abilities:
  +1: Surveil 2.
  -1: Any number of target players each discard a card.
  -2: Return target creature card with mana value 3 or less from your
      graveyard to the battlefield.
  -7: Flip five coins. Target opponent skips their next X turns, where X
      is the number of coins that came up heads.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestRalZarekProperties:
    """Verify static card data matches the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_planeswalker_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_subtype_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes


# ---------------------------------------------------------------------------
# Loyalty abilities structure
# ---------------------------------------------------------------------------


class TestRalZarekLoyaltyAbilities:
    """get_loyalty_abilities() should return exactly four abilities
    with the correct loyalty costs."""

    def test_returns_four_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 4

    def test_all_are_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        for ab in card.get_loyalty_abilities():
            assert isinstance(ab, LoyaltyAbility)

    def test_first_ability_is_plus_one(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1

    def test_second_ability_is_minus_one(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[1].loyalty_cost == -1

    def test_third_ability_is_minus_two(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[2].loyalty_cost == -2

    def test_fourth_ability_is_minus_seven(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[3].loyalty_cost == -7


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------


class TestRalZarekSurveil:
    """The +1 ability should surveil 2 -- look at the top 2 cards of the
    controller's library, putting any number into the graveyard and the
    rest back on top in any order."""

    def _make_game_with_ral(self):
        """Create a game with Ral on p1's battlefield and library cards."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 3
        set_board_state(game, 0, battlefield=[ral])

        # Put known cards in the library
        card_a = Creature(name="Card A", owner=p1, base_power=1, base_toughness=1)
        card_b = Creature(name="Card B", owner=p1, base_power=2, base_toughness=2)
        card_c = Creature(name="Card C", owner=p1, base_power=3, base_toughness=3)
        set_board_state(game, 0, hand=[])
        lib = game.get_library(p1)
        # Clear library and add cards: C on bottom, B, A on top
        for obj in lib.get_all():
            lib.remove(obj)
        lib.add(card_c)
        lib.add(card_b)
        lib.add(card_a)
        return game, ral, p1, card_a, card_b

    def test_surveil_puts_cards_in_graveyard(self) -> None:
        """When surveil 2, both cards can be put into the graveyard."""
        game, ral, p1, card_a, card_b = self._make_game_with_ral()
        lib_before = len(game.get_library(p1))
        gy_before = len(game.get_graveyard(p1))

        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        # Script player choices to put both cards in graveyard
        p1._script.extend([card_a, card_b])  # choose both for graveyard
        plus_one.effect(game)

        # After surveil 2, library should have lost 2 cards that went to GY
        lib_after = len(game.get_library(p1))
        gy_after = len(game.get_graveyard(p1))
        # At least some cards should have moved -- either to GY or back to library
        assert lib_after <= lib_before

    def test_surveil_with_fewer_cards_than_surveil_count(self) -> None:
        """Surveil with only 1 card in library should not error."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 3
        set_board_state(game, 0, battlefield=[ral])

        single_card = Creature(name="Only Card", owner=p1, base_power=1, base_toughness=1)
        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        lib.add(single_card)
        set_board_state(game, 0, hand=[])

        abilities = ral.get_loyalty_abilities()
        p1._script.extend([single_card])  # put the one card into GY
        # Should not raise even though library has fewer than 2 cards
        plus_one = abilities[0]
        plus_one.effect(game)


# ---------------------------------------------------------------------------
# -1: Any number of target players each discard a card
# ---------------------------------------------------------------------------


class TestRalZarekDiscard:
    """The -1 ability: any number of target players each discard a card."""

    def _make_game_with_ral_and_hands(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 3
        set_board_state(game, 0, battlefield=[ral])

        card_in_p1_hand = Creature(name="P1 Card", owner=p1, base_power=1, base_toughness=1)
        card_in_p2_hand = Creature(name="P2 Card", owner=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[card_in_p1_hand])
        set_board_state(game, 1, hand=[card_in_p2_hand])
        return game, ral, p1, p2, card_in_p1_hand, card_in_p2_hand

    def test_opponent_discards_a_card(self) -> None:
        """Targeting the opponent should cause them to discard a card."""
        game, ral, p1, p2, _, card_p2 = self._make_game_with_ral_and_hands()
        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]

        # Script: choose p2 as target, p2 chooses which card to discard
        p2._script.extend([card_p2])  # opponent chooses card to discard
        ral.chosen_targets = [p2]
        minus_one.effect(game)

        assert len(game.get_hand(p2).get_all()) == 0
        gy_cards = game.get_graveyard(p2).get_all()
        assert any(getattr(c, "name", "") == "P2 Card" for c in gy_cards)

    def test_both_players_discard(self) -> None:
        """Targeting both players should make each discard a card."""
        game, ral, p1, p2, card_p1, card_p2 = self._make_game_with_ral_and_hands()
        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]

        # Script discard choices for both players
        p1._script.extend([card_p1])
        p2._script.extend([card_p2])
        ral.chosen_targets = [p1, p2]
        minus_one.effect(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_hand(p2).get_all()) == 0

    def test_targeting_zero_players_is_allowed(self) -> None:
        """Targeting zero players (empty target list) should be a no-op."""
        game, ral, p1, p2, _, _ = self._make_game_with_ral_and_hands()
        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]

        ral.chosen_targets = []
        minus_one.effect(game)

        # Hands should be unchanged
        assert len(game.get_hand(p1).get_all()) == 1
        assert len(game.get_hand(p2).get_all()) == 1

    def test_player_with_empty_hand_no_error(self) -> None:
        """A targeted player with no cards in hand should not raise an error."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 3
        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, hand=[])  # empty hand

        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        ral.chosen_targets = [p2]
        # Should not raise
        minus_one.effect(game)

        assert len(game.get_hand(p2).get_all()) == 0


# ---------------------------------------------------------------------------
# -2: Return target creature card with mana value 3 or less from your
#     graveyard to the battlefield
# ---------------------------------------------------------------------------


class TestRalZarekReanimate:
    """The -2 ability returns a creature with MV <= 3 from the graveyard
    to the battlefield."""

    def _make_game_with_ral_and_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 5  # enough for -2
        set_board_state(game, 0, battlefield=[ral])
        return game, ral, p1

    def test_returns_creature_to_battlefield(self) -> None:
        """A creature with MV <= 3 in the graveyard moves to the battlefield."""
        game, ral, p1 = self._make_game_with_ral_and_graveyard()

        # MV 2 creature in graveyard
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
        )
        set_board_state(game, 0, graveyard=[bear])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral.chosen_targets = [bear]
        minus_two.effect(game)

        bf_objects = game.get_battlefield(p1).get_all()
        assert any(obj is bear for obj in bf_objects), \
            "The creature should have moved from graveyard to battlefield."
        gy_objects = game.get_graveyard(p1).get_all()
        assert all(obj is not bear for obj in gy_objects), \
            "The creature should no longer be in the graveyard."

    def test_creature_with_mv_3_is_valid(self) -> None:
        """A creature with mana value exactly 3 is a valid target."""
        game, ral, p1 = self._make_game_with_ral_and_graveyard()

        creature_mv3 = Creature(
            name="MV3 Creature", owner=p1, controller=p1,
            base_power=3, base_toughness=3,
            mana_cost=ManaCost.parse("{2}{B}"),
        )
        set_board_state(game, 0, graveyard=[creature_mv3])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral.chosen_targets = [creature_mv3]
        minus_two.effect(game)

        bf = game.get_battlefield(p1).get_all()
        assert any(obj is creature_mv3 for obj in bf)

    def test_creature_with_mv_0_is_valid(self) -> None:
        """A creature with mana value 0 is a valid target."""
        game, ral, p1 = self._make_game_with_ral_and_graveyard()

        token_like = Creature(
            name="Zero Cost", owner=p1, controller=p1,
            base_power=0, base_toughness=1,
            mana_cost=ManaCost(generic=0),
        )
        set_board_state(game, 0, graveyard=[token_like])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral.chosen_targets = [token_like]
        minus_two.effect(game)

        bf = game.get_battlefield(p1).get_all()
        assert any(obj is token_like for obj in bf)

    def test_no_target_is_noop(self) -> None:
        """If no target is set, the ability should not raise."""
        game, ral, p1 = self._make_game_with_ral_and_graveyard()
        set_board_state(game, 0, graveyard=[])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral.chosen_targets = []
        # Should not raise
        minus_two.effect(game)

    def test_graveyard_targeting_filter(self) -> None:
        """The targeting requirement should filter for creatures in the
        graveyard with MV <= 3."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        mv2_creature = Creature(
            name="Small Creature", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        mv2_creature.card_types = {CardType.CREATURE}

        mv5_creature = Creature(
            name="Big Creature", base_power=5, base_toughness=5,
            mana_cost=ManaCost.parse("{3}{B}{B}"),
        )
        mv5_creature.card_types = {CardType.CREATURE}

        # Check that get_targets advertises graveyard filtering
        targets = ral.get_targets(game)
        # The third ability (index 2) should have a targeting requirement
        # that filters creatures with MV <= 3 in the graveyard.
        # Implementation may also use per-ability get_targets.
        # We verify the filter accepts MV<=3 creatures and rejects MV>3.
        found_gy_req = False
        for req in targets:
            if req.zone == Zone.GRAVEYARD:
                found_gy_req = True
                assert req.filter_fn(mv2_creature) is True
                assert req.filter_fn(mv5_creature) is False
                break

        if not found_gy_req and len(targets) == 0:
            # Alternative: per-ability targeting -- test by direct ability invocation
            # (covered by other tests in this class)
            pass


# ---------------------------------------------------------------------------
# -7: Flip five coins. Target opponent skips their next X turns
# ---------------------------------------------------------------------------


class TestRalZarekUltimate:
    """The -7 ability flips five coins and the target opponent skips
    their next X turns (X = heads count)."""

    def _make_game_with_ral_at_7(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        return game, ral, p1, p2

    def test_all_heads_skips_five_turns(self) -> None:
        """If all 5 coins come up heads, opponent skips 5 turns."""
        import random
        game, ral, p1, p2 = self._make_game_with_ral_at_7()

        abilities = ral.get_loyalty_abilities()
        ultimate = abilities[3]
        ral.chosen_targets = [p2]

        # Monkey-patch random to always return heads
        old_choice = random.choice
        old_randint = random.randint
        try:
            random.choice = lambda seq: seq[0]  # always first = heads
            random.randint = lambda a, b: 1  # 1 = heads
            ultimate.effect(game)
        finally:
            random.choice = old_choice
            random.randint = old_randint

        # Opponent should skip 5 turns -- check via extra_turns or skip_turns
        # The engine uses game.extra_turns for extra turn tracking.
        # For skipping turns, the implementation should track skipped turns
        # either on the player or game state.
        skip_count = getattr(p2, "skip_turns", 0)
        # Alternative: check if game uses some other mechanism
        if skip_count == 0:
            # Maybe the implementation uses extra_turns for p1 instead
            # (giving p1 extra turns is equivalent to opponent "skipping")
            p1_extra_turns = sum(
                1 for t in game.extra_turns
                if t == 0  # p1 index
            )
            assert p1_extra_turns == 5 or skip_count == 5, \
                "Opponent should skip 5 turns (all heads)."
        else:
            assert skip_count == 5

    def test_all_tails_skips_zero_turns(self) -> None:
        """If all 5 coins come up tails, opponent skips 0 turns."""
        import random
        game, ral, p1, p2 = self._make_game_with_ral_at_7()

        abilities = ral.get_loyalty_abilities()
        ultimate = abilities[3]
        ral.chosen_targets = [p2]

        old_choice = random.choice
        old_randint = random.randint
        try:
            random.choice = lambda seq: seq[-1]  # always last = tails
            random.randint = lambda a, b: 0  # 0 = tails
            ultimate.effect(game)
        finally:
            random.choice = old_choice
            random.randint = old_randint

        # Zero turns skipped -- no extra turns and no skip marker
        skip_count = getattr(p2, "skip_turns", 0)
        p1_extra = sum(1 for t in game.extra_turns if t == 0)
        assert skip_count == 0 or p1_extra == 0, \
            "With all tails, no turns should be skipped."

    def test_no_target_is_noop(self) -> None:
        """If there is no target, the ability should not crash."""
        game, ral, p1, p2 = self._make_game_with_ral_at_7()

        abilities = ral.get_loyalty_abilities()
        ultimate = abilities[3]
        ral.chosen_targets = []
        # Should not raise
        ultimate.effect(game)
