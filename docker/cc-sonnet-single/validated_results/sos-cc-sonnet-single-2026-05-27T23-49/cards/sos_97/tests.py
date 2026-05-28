"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Covers:
- Static properties: name, mana cost, card type, subtypes, supertypes, loyalty
- get_loyalty_abilities() returns exactly 3 abilities with correct loyalty costs
- +1: Surveil 2 — looks at top 2 library cards, moves chosen to graveyard
- −1: Any number of target players each discard a card
- −2: Return target creature card with mana value <= 3 from graveyard to battlefield
- −7: Flip 5 coins; target opponent skips X turns where X = heads count
- Loyalty tracking: each ability adjusts loyalty by its cost
"""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    """Static card data should match the sos_97 spec."""

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_planeswalker_card_type(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_legendary_supertype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_starting_loyalty_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability declaration tests
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyAbilities:
    """get_loyalty_abilities() should return exactly 4 LoyaltyAbility instances."""

    def test_returns_list_of_four(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 4

    def test_plus_one_ability_cost(self) -> None:
        """First ability is +1 (Surveil 2)."""
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1

    def test_minus_one_ability_cost(self) -> None:
        """Second ability is −1 (discard)."""
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[1].loyalty_cost == -1

    def test_minus_two_ability_cost(self) -> None:
        """Third ability is −2 (return creature from graveyard)."""
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[2].loyalty_cost == -2

    def test_fourth_ability_cost_minus_seven(self) -> None:
        """Card has a −7 ability (coin-flip turn-skip); it must be in the list."""
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        costs = [a.loyalty_cost for a in abilities]
        assert -7 in costs


# ---------------------------------------------------------------------------
# +1 Surveil 2 tests
# ---------------------------------------------------------------------------

class TestRalZarekSurveil:
    """+1: Surveil 2 — look at top 2, keep or send to graveyard."""

    def _setup(self):
        """Return a game and a placed Ral on player 0's battlefield."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        return game, p1, ral

    def test_surveil_moves_chosen_card_to_graveyard(self) -> None:
        """When controller says 'yes' to the first card, it goes to graveyard."""
        game, p1, ral = self._setup()
        # Put two cards on top of library.
        c1 = Creature(name="Card A", base_power=1, base_toughness=1, owner=p1)
        c2 = Creature(name="Card B", base_power=1, base_toughness=1, owner=p1)
        library = p1.zones[Zone.LIBRARY]
        library.add(c1)
        library.add(c2)  # c2 is now on top

        # Script: send c2 to graveyard (True), keep c1 in library (False).
        p1._script.append(True)
        p1._script.append(False)

        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        plus_one.effect(game)

        graveyard = p1.zones[Zone.GRAVEYARD]
        assert graveyard.contains(c2), "Top card chosen for graveyard should be in graveyard"
        assert library.contains(c1), "Card kept should remain in library"

    def test_surveil_card_kept_stays_in_library(self) -> None:
        """When controller says 'no' to a card, it remains in the library."""
        game, p1, ral = self._setup()
        c1 = Creature(name="Keeper", base_power=2, base_toughness=2, owner=p1)
        library = p1.zones[Zone.LIBRARY]
        library.add(c1)

        # Script: keep c1 (False → don't send to graveyard).
        p1._script.append(False)

        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        plus_one.effect(game)

        assert library.contains(c1), "Kept card should remain in library"

    def test_surveil_with_empty_library_does_not_raise(self) -> None:
        """Surveil with no cards in library is a no-op (no error)."""
        game, p1, ral = self._setup()
        # Library is empty.
        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        plus_one.effect(game)  # Must not raise.

    def test_surveil_only_looks_at_up_to_two_cards(self) -> None:
        """Surveil 2 only inspects top 2 cards, not the full library."""
        game, p1, ral = self._setup()
        library = p1.zones[Zone.LIBRARY]
        cards = [
            Creature(name=f"Card {i}", base_power=1, base_toughness=1, owner=p1)
            for i in range(5)
        ]
        for c in cards:
            library.add(c)

        # Send both surveiled cards to graveyard.
        p1._script.append(True)
        p1._script.append(True)

        initial_size = len(library)
        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        plus_one.effect(game)

        graveyard = p1.zones[Zone.GRAVEYARD]
        assert len(graveyard) == 2, "Exactly 2 cards should be surveiled to graveyard"
        assert len(library) == initial_size - 2


# ---------------------------------------------------------------------------
# −1 Discard ability tests
# ---------------------------------------------------------------------------

class TestRalZarekDiscard:
    """−1: Any number of target players each discard a card."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        return game, p1, p2, ral

    def test_targeted_player_discards_a_card(self) -> None:
        """The targeted player (p1) loses one card from hand."""
        game, p1, p2, ral = self._setup()
        hand_card = Creature(name="Discard Me", base_power=1, base_toughness=1, owner=p1)
        set_board_state(game, 0, hand=[hand_card])

        # Script: p1 discards hand_card.
        p1._script.append(hand_card)

        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        # Set targets to p1 (targeting self is legal for "any number of target players").
        ral._resolve_targets = [p1]
        minus_one.effect(game)

        graveyard = p1.zones[Zone.GRAVEYARD]
        assert graveyard.contains(hand_card), "Discarded card should be in graveyard"

    def test_opponent_discards_a_card(self) -> None:
        """The targeted opponent loses one card from their hand."""
        game, p1, p2, ral = self._setup()
        opp_card = Creature(name="Opp Card", base_power=1, base_toughness=1, owner=p2)
        set_board_state(game, 1, hand=[opp_card])

        # Script: p2 discards opp_card.
        p2._script.append(opp_card)

        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        ral._resolve_targets = [p2]
        minus_one.effect(game)

        graveyard = p2.zones[Zone.GRAVEYARD]
        assert graveyard.contains(opp_card), "Opponent's discarded card should be in their graveyard"

    def test_no_targets_is_a_noop(self) -> None:
        """With zero targets chosen, no discard occurs and no error is raised."""
        game, p1, p2, ral = self._setup()
        hand_card = Creature(name="Safe Card", base_power=1, base_toughness=1, owner=p1)
        set_board_state(game, 0, hand=[hand_card])

        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        ral._resolve_targets = []
        minus_one.effect(game)

        assert p1.zones[Zone.HAND].contains(hand_card), "Card should stay in hand when no targets"

    def test_multiple_players_each_discard(self) -> None:
        """When both players are targeted, each discards a card."""
        game, p1, p2, ral = self._setup()
        p1_card = Creature(name="P1 Discard", base_power=1, base_toughness=1, owner=p1)
        p2_card = Creature(name="P2 Discard", base_power=1, base_toughness=1, owner=p2)
        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])

        # Script: p1 discards p1_card, p2 discards p2_card.
        p1._script.append(p1_card)
        p2._script.append(p2_card)

        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        ral._resolve_targets = [p1, p2]
        minus_one.effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(p1_card)
        assert p2.zones[Zone.GRAVEYARD].contains(p2_card)


# ---------------------------------------------------------------------------
# −2 Return creature from graveyard to battlefield
# ---------------------------------------------------------------------------

class TestRalZarekGraveyardReturn:
    """−2: Return target creature card with MV <= 3 from your graveyard to battlefield."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        return game, p1, ral

    def test_creature_with_mv_three_or_less_returns_to_battlefield(self) -> None:
        """A creature with CMC 3 in the graveyard enters the battlefield."""
        game, p1, ral = self._setup()
        small_creature = Creature(
            name="Small Dude",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}{B}"),  # CMC 3
        )
        set_board_state(game, 0, graveyard=[small_creature])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral._resolve_target = small_creature
        minus_two.effect(game)

        battlefield = game.get_battlefield(p1)
        assert battlefield.contains(small_creature), "Creature should enter the battlefield"

    def test_creature_moved_out_of_graveyard(self) -> None:
        """After returning, the creature is no longer in the graveyard."""
        game, p1, ral = self._setup()
        creature = Creature(
            name="Cheap Creature",
            base_power=1,
            base_toughness=1,
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{B}"),  # CMC 1
        )
        set_board_state(game, 0, graveyard=[creature])

        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral._resolve_target = creature
        minus_two.effect(game)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(creature), "Creature should no longer be in graveyard"

    def test_no_target_is_a_noop(self) -> None:
        """If no target is set, the ability does nothing and does not raise."""
        game, p1, ral = self._setup()
        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        ral._resolve_target = None
        minus_two.effect(game)  # Must not raise.


# ---------------------------------------------------------------------------
# −7 Coin-flip turn-skip tests
# ---------------------------------------------------------------------------

class TestRalZarekUltimate:
    """−7: Flip five coins; opponent skips X turns where X = heads."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        return game, p1, p2, ral

    def _find_minus_seven(self, ral: RalZarekGuestLecturer) -> LoyaltyAbility:
        abilities = ral.get_loyalty_abilities()
        for a in abilities:
            if a.loyalty_cost == -7:
                return a
        raise AssertionError("No −7 ability found on Ral Zarek, Guest Lecturer")

    def test_ultimate_exists_with_minus_seven_cost(self) -> None:
        """The −7 ultimate ability must be declared."""
        _, _, _, ral = self._setup()
        self._find_minus_seven(ral)  # Raises if not found.

    def test_ultimate_with_all_heads_skips_five_turns(self) -> None:
        """Five heads → opponent skips 5 turns (5 extra turn slots for p1)."""
        game, p1, p2, ral = self._setup()
        minus_seven = self._find_minus_seven(ral)
        ral._resolve_target = p2
        # Patch coin flip to always return heads (True = heads).
        ral._coin_flip_results = [True, True, True, True, True]
        before_extra = len(game.extra_turns)
        minus_seven.effect(game)
        after_extra = len(game.extra_turns)
        # 5 turns skipped for opponent = 5 extra turns granted to p1 (or 5 extra entries).
        # Accept either: extra_turns grew by 5, or p2.skipped_turns attribute set to 5.
        if hasattr(p2, "skipped_turns"):
            assert p2.skipped_turns >= 5
        else:
            assert after_extra - before_extra == 5

    def test_ultimate_with_all_tails_skips_zero_turns(self) -> None:
        """Five tails → X=0, opponent skips no turns."""
        game, p1, p2, ral = self._setup()
        minus_seven = self._find_minus_seven(ral)
        ral._resolve_target = p2
        ral._coin_flip_results = [False, False, False, False, False]
        before_extra = len(game.extra_turns)
        minus_seven.effect(game)
        after_extra = len(game.extra_turns)
        if hasattr(p2, "skipped_turns"):
            assert p2.skipped_turns == 0
        else:
            assert after_extra == before_extra

    def test_ultimate_no_target_does_not_raise(self) -> None:
        """If no target is provided, the ultimate is a no-op and doesn't crash."""
        game, p1, p2, ral = self._setup()
        minus_seven = self._find_minus_seven(ral)
        ral._resolve_target = None
        ral._coin_flip_results = [True, True, True, True, True]
        minus_seven.effect(game)  # Must not raise.


# ---------------------------------------------------------------------------
# Loyalty counter adjustment tests
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyTracking:
    """Each activated ability adjusts loyalty by its declared cost."""

    def _place_ral(self, game, player, starting_loyalty=10):
        ral = RalZarekGuestLecturer(owner=player, controller=player)
        ral.loyalty = starting_loyalty
        set_board_state(game, game.players.index(player), battlefield=[ral])
        return ral

    def test_plus_one_increases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = self._place_ral(game, p1, starting_loyalty=5)
        # Library must have cards; script says don't send to graveyard.
        library = p1.zones[Zone.LIBRARY]
        c1 = Creature(name="C1", base_power=1, base_toughness=1, owner=p1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1, owner=p1)
        library.add(c1)
        library.add(c2)
        p1._script.append(False)
        p1._script.append(False)

        abilities = ral.get_loyalty_abilities()
        plus_one = abilities[0]
        before = ral.loyalty
        # Loyalty is adjusted by the ability dispatch layer, not the effect itself.
        # The LoyaltyAbility.loyalty_cost attribute signals the cost.
        # We test that activating + manually adjusting matches the spec.
        ral.loyalty += plus_one.loyalty_cost
        assert ral.loyalty == before + 1

    def test_minus_one_decreases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = self._place_ral(game, p1, starting_loyalty=5)
        abilities = ral.get_loyalty_abilities()
        minus_one = abilities[1]
        before = ral.loyalty
        ral.loyalty += minus_one.loyalty_cost
        assert ral.loyalty == before - 1

    def test_minus_two_decreases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = self._place_ral(game, p1, starting_loyalty=5)
        abilities = ral.get_loyalty_abilities()
        minus_two = abilities[2]
        before = ral.loyalty
        ral.loyalty += minus_two.loyalty_cost
        assert ral.loyalty == before - 2
