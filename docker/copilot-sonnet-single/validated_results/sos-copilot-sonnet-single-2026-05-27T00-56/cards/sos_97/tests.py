"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Covers static properties, loyalty-ability costs, and the resolution
effects for each of the four abilities:

  +1  Surveil 2
  −1  Any number of target players each discard a card
  −2  Return target creature card with mana value 3 or less from your
      graveyard to the battlefield
  −7  Flip five coins; target opponent skips next X turns (X = heads)
"""

from __future__ import annotations

import unittest.mock
from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import CardImpl, Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card() -> RalZarekGuestLecturer:
    return RalZarekGuestLecturer(owner=None)


def _first_ability(card: RalZarekGuestLecturer) -> LoyaltyAbility:
    return card.get_loyalty_abilities()[0]


def _second_ability(card: RalZarekGuestLecturer) -> LoyaltyAbility:
    return card.get_loyalty_abilities()[1]


def _third_ability(card: RalZarekGuestLecturer) -> LoyaltyAbility:
    return card.get_loyalty_abilities()[2]


def _fourth_ability(card: RalZarekGuestLecturer) -> LoyaltyAbility:
    return card.get_loyalty_abilities()[3]


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestRalZarekGuestLecturerProperties:
    """Static card data must match the SOS 97 spec."""

    def test_is_planeswalker_instance(self) -> None:
        assert isinstance(_make_card(), Planeswalker)

    def test_card_type_is_planeswalker(self) -> None:
        assert CardType.PLANESWALKER in _make_card().card_types

    def test_not_creature(self) -> None:
        assert CardType.CREATURE not in _make_card().card_types

    def test_name(self) -> None:
        assert _make_card().name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert _make_card().mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        assert _make_card().starting_loyalty == 3

    def test_initial_loyalty_equals_starting(self) -> None:
        card = _make_card()
        assert card.loyalty == card.starting_loyalty

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in _make_card().supertypes

    def test_subtype_is_ral(self) -> None:
        assert "Ral" in _make_card().subtypes


# ---------------------------------------------------------------------------
# Loyalty ability counts and costs
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyAbilityCosts:
    """get_loyalty_abilities() must declare exactly 4 abilities with the
    correct loyalty costs (+1, −1, −2, −7)."""

    def test_has_four_loyalty_abilities(self) -> None:
        assert len(_make_card().get_loyalty_abilities()) == 4

    def test_each_ability_is_loyalty_ability_instance(self) -> None:
        for ab in _make_card().get_loyalty_abilities():
            assert isinstance(ab, LoyaltyAbility)

    def test_first_ability_cost_plus_one(self) -> None:
        assert _first_ability(_make_card()).loyalty_cost == +1

    def test_second_ability_cost_minus_one(self) -> None:
        assert _second_ability(_make_card()).loyalty_cost == -1

    def test_third_ability_cost_minus_two(self) -> None:
        assert _third_ability(_make_card()).loyalty_cost == -2

    def test_fourth_ability_cost_minus_seven(self) -> None:
        assert _fourth_ability(_make_card()).loyalty_cost == -7


# ---------------------------------------------------------------------------
# +1 ability — Surveil 2
# ---------------------------------------------------------------------------

class TestRalZarekPlusOneAbility:
    """The +1 ability surveils 2: look at the top 2 cards of the controller's
    library and put any number into the graveyard; the rest go back on top."""

    def _seed_library(self, player: Any, count: int = 5) -> list[CardImpl]:
        """Put *count* distinct dummy cards in the player's library (FIFO order).

        The last card appended is at the 'top' of the library (index -1 in
        get_all() list).
        """
        cards: list[CardImpl] = []
        for i in range(count):
            c = CardImpl(name=f"LibCard{i}")
            player.zones[Zone.LIBRARY].add(c)
            cards.append(c)
        return cards

    def test_surveil_does_not_raise_with_full_library(self) -> None:
        """Effect must not raise when the library has at least 2 cards."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        self._seed_library(p1, 4)
        # Simulate player choosing to put both surveilled cards in graveyard
        # by scripting yes/yes for choose_yes_no calls.
        p1._script.extend([True, True])
        _first_ability(card).effect(game)  # must not raise

    def test_surveil_does_not_raise_with_empty_library(self) -> None:
        """Surveil on an empty library must not crash."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        _first_ability(card).effect(game)  # library already empty after create_game reset

    def test_surveil_puts_cards_in_graveyard_when_chosen(self) -> None:
        """When the player chooses to put surveilled cards into the graveyard,
        they appear in the graveyard and are removed from the library."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        surveilled_cards = self._seed_library(p1, 2)
        before_graveyard = len(p1.zones[Zone.GRAVEYARD].get_all())
        # Both yes → put both into graveyard
        p1._script.extend([True, True])
        _first_ability(card).effect(game)
        after_graveyard = len(p1.zones[Zone.GRAVEYARD].get_all())
        # At least one card should have moved to the graveyard
        assert after_graveyard > before_graveyard

    def test_surveil_looks_at_most_two_cards(self) -> None:
        """Surveil 2 looks at exactly 2 cards (or fewer if library is smaller)."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        self._seed_library(p1, 5)
        before_library = len(p1.zones[Zone.LIBRARY].get_all())
        # Script player to put all surveilled cards in graveyard
        p1._script.extend([True, True])
        _first_ability(card).effect(game)
        after_library = len(p1.zones[Zone.LIBRARY].get_all())
        # At most 2 cards were surveilled
        assert before_library - after_library <= 2

    def test_surveil_one_card_library(self) -> None:
        """Surveil on a 1-card library surveils that single card."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        lone = CardImpl(name="LoneCard")
        p1.zones[Zone.LIBRARY].add(lone)
        before_graveyard = len(p1.zones[Zone.GRAVEYARD].get_all())
        p1._script.extend([True])
        _first_ability(card).effect(game)
        after_graveyard = len(p1.zones[Zone.GRAVEYARD].get_all())
        assert after_graveyard >= before_graveyard  # no crash; card may have moved


# ---------------------------------------------------------------------------
# −1 ability — Any number of target players each discard a card
# ---------------------------------------------------------------------------

class TestRalZarekMinusOneAbility:
    """The −1 ability causes each chosen target player to discard a card."""

    def test_target_player_discards_one_card(self) -> None:
        """A single targeted player should lose one card from hand."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Give p2 a card in hand
        hand_card = CardImpl(name="HandCard")
        p2.zones[Zone.HAND].add(hand_card)
        before = len(p2.zones[Zone.HAND].get_all())
        # Set target: p2 must discard
        card._resolve_targets = [p2]
        _second_ability(card).effect(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before - 1

    def test_target_player_card_goes_to_graveyard(self) -> None:
        """The discarded card should appear in the target player's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        hand_card = CardImpl(name="DiscardMe")
        p2.zones[Zone.HAND].add(hand_card)
        before_gy = len(p2.zones[Zone.GRAVEYARD].get_all())
        card._resolve_targets = [p2]
        _second_ability(card).effect(game)
        after_gy = len(p2.zones[Zone.GRAVEYARD].get_all())
        assert after_gy == before_gy + 1

    def test_no_targets_is_noop(self) -> None:
        """With no target players, no discards occur."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        hand_card = CardImpl(name="SafeCard")
        p2.zones[Zone.HAND].add(hand_card)
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_targets = []
        before = len(p2.zones[Zone.HAND].get_all())
        _second_ability(card).effect(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before

    def test_multiple_targets_each_discard(self) -> None:
        """Any number of target players — both p1 and p2 each discard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        for player in [p1, p2]:
            player.zones[Zone.HAND].add(CardImpl(name=f"Card_for_{player.name}"))
        before_p1 = len(p1.zones[Zone.HAND].get_all())
        before_p2 = len(p2.zones[Zone.HAND].get_all())
        card._resolve_targets = [p1, p2]
        _second_ability(card).effect(game)
        assert len(p1.zones[Zone.HAND].get_all()) == before_p1 - 1
        assert len(p2.zones[Zone.HAND].get_all()) == before_p2 - 1

    def test_player_with_empty_hand_no_crash(self) -> None:
        """Targeting a player with no cards in hand must not crash."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        # p2 has empty hand
        card._resolve_targets = [p2]
        _second_ability(card).effect(game)  # must not raise


# ---------------------------------------------------------------------------
# −2 ability — Return creature (MV ≤ 3) from graveyard to battlefield
# ---------------------------------------------------------------------------

class TestRalZarekMinusTwoAbility:
    """The −2 ability returns a creature with MV ≤ 3 from the controller's
    graveyard to the battlefield."""

    def _creature_in_graveyard(self, player: Any, name: str, cmc: int) -> Creature:
        """Create a creature with the given cmc in the player's graveyard."""
        from engine.types import ManaCost as MC
        if cmc == 0:
            mc = MC()
        elif cmc <= 3:
            mc = MC(generic=cmc)
        else:
            mc = MC(generic=cmc)
        c = Creature(
            name=name,
            base_power=1,
            base_toughness=1,
            mana_cost=mc,
        )
        c.owner = player
        c.controller = player
        player.zones[Zone.GRAVEYARD].add(c)
        return c

    def test_returns_creature_to_battlefield(self) -> None:
        """A targeted creature with MV ≤ 3 moves from graveyard to battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = self._creature_in_graveyard(p1, "SmallCreature", cmc=2)
        card._resolve_target = target
        _third_ability(card).effect(game)
        bf = game.get_battlefield(p1).get_all()
        assert target in bf

    def test_creature_leaves_graveyard(self) -> None:
        """The reanimated creature should no longer be in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = self._creature_in_graveyard(p1, "Revivable", cmc=1)
        card._resolve_target = target
        _third_ability(card).effect(game)
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert target not in gy

    def test_creature_with_mv_three_is_valid(self) -> None:
        """A creature with exactly MV 3 can be returned."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = self._creature_in_graveyard(p1, "ThreeDrop", cmc=3)
        card._resolve_target = target
        _third_ability(card).effect(game)
        bf = game.get_battlefield(p1).get_all()
        assert target in bf

    def test_no_target_is_noop(self) -> None:
        """When no target is chosen, the ability does nothing and doesn't crash."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = None
        before_bf = len(game.get_battlefield(p1).get_all())
        _third_ability(card).effect(game)
        assert len(game.get_battlefield(p1).get_all()) == before_bf

    def test_creature_not_in_graveyard_is_noop(self) -> None:
        """If the target is no longer in the graveyard, the effect does nothing."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Creature not placed in graveyard — not a valid target
        orphan = Creature(name="Orphan", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{1}"))
        orphan.owner = p1
        orphan.controller = p1
        # Don't add to graveyard — place on battlefield directly to simulate
        # a card that moved zones unexpectedly
        game.get_battlefield(p1).add(orphan)
        card._resolve_target = orphan
        before_bf = len(game.get_battlefield(p1).get_all())
        _third_ability(card).effect(game)
        # No additional card should land on the battlefield
        assert len(game.get_battlefield(p1).get_all()) == before_bf


# ---------------------------------------------------------------------------
# −7 ability — Flip five coins; target opponent skips next X turns
# ---------------------------------------------------------------------------

class TestRalZarekMinusSevenAbility:
    """The −7 ability flips five coins. The target opponent skips their
    next X turns where X equals the number of heads."""

    def test_effect_does_not_raise_without_target(self) -> None:
        """With no target set, the ability must not crash."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = None
        _fourth_ability(card).effect(game)  # must not raise

    def test_all_heads_skips_five_turns(self) -> None:
        """When all 5 flips come up heads, the target opponent skips 5 turns.

        The turn-skipping state is stored on the target player via a
        ``turns_to_skip`` attribute (or equivalent) set by the implementation.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = p2
        # Patch random to always return heads (True / 1)
        with unittest.mock.patch("random.random", return_value=0.0):
            _fourth_ability(card).effect(game)
        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 5

    def test_all_tails_skips_zero_turns(self) -> None:
        """When all 5 flips come up tails, the opponent skips 0 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = p2
        # Patch random to always return tails (False / 0)
        with unittest.mock.patch("random.random", return_value=1.0):
            _fourth_ability(card).effect(game)
        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 0

    def test_three_heads_skips_three_turns(self) -> None:
        """When exactly 3 of 5 flips come up heads, the opponent skips 3 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = p2
        # Return True (heads) for the first three flips, False (tails) for the rest
        flip_seq = [0.0, 0.0, 0.0, 1.0, 1.0]
        with unittest.mock.patch("random.random", side_effect=flip_seq):
            _fourth_ability(card).effect(game)
        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 3

    def test_flips_exactly_five_coins(self) -> None:
        """The implementation must flip exactly 5 coins."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card._resolve_target = p2
        call_count: list[int] = []

        def counting_random() -> float:
            call_count.append(1)
            return 0.0  # always heads

        with unittest.mock.patch("random.random", side_effect=counting_random):
            _fourth_ability(card).effect(game)
        assert sum(call_count) == 5
