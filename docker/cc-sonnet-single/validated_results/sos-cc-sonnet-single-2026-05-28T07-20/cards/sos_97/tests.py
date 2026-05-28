"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Coverage:
- Static properties: name, mana cost, Planeswalker type/subtypes, starting loyalty
- +1 ability: surveil 2 (top cards optionally to graveyard, rest on library)
- +1 ability: loyalty increases from 3 to 4
- -1 ability: loyalty decreases from 3 to 2; each targeted player discards
- -1 ability: "any number of target players" — works for 0, 1, or 2 players
- -2 ability: loyalty decreases from 3 to 1; creature with mana value ≤3 from
  controller's graveyard is returned to the battlefield
- -2 ability: does NOT return a creature with mana value > 3
- -7 ability: loyalty decreases from 3 to -4 (needs starting loyalty ≥ 7 or test
  with inflated loyalty); coins flipped, opponent skips X turns where X = heads
"""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creature(name: str, cmc: int = 2, owner=None, controller=None) -> Creature:
    """Create a minimal creature with a predictable mana cost for mana value testing."""
    cost = ManaCost(generic=cmc) if cmc > 0 else ManaCost()
    c = Creature(
        name=name,
        mana_cost=cost,
        base_power=2,
        base_toughness=2,
        owner=owner,
        controller=controller,
    )
    return c


def _activate_loyalty_ability(pw: RalZarekGuestLecturer, ability_index: int, game) -> None:
    """Activate the nth loyalty ability on pw (0-indexed), adjusting loyalty."""
    abilities = pw.get_loyalty_abilities()
    ability = abilities[ability_index]
    pw.loyalty += ability.loyalty_cost
    ability.effect(game)


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

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

    def test_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_legendary_supertype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_starting_loyalty_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_initial_loyalty_equals_starting(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == card.starting_loyalty

    def test_exposes_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) == 4  # +1, -1, -2, -7

    def test_loyalty_ability_types(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        for ability in card.get_loyalty_abilities():
            assert isinstance(ability, LoyaltyAbility)

    def test_ability_loyalty_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert +1 in costs
        assert -1 in costs
        assert -2 in costs
        assert -7 in costs


# ---------------------------------------------------------------------------
# +1 ability: Surveil 2 — loyalty adjustment
# ---------------------------------------------------------------------------


class TestRalZarekPlusOneAbility:
    """The +1 ability: Surveil 2, and loyalty goes from 3 → 4."""

    def test_plus1_increases_loyalty_from_3_to_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        assert pw.loyalty == 3
        _activate_loyalty_ability(pw, 0, game)
        assert pw.loyalty == 4

    def test_plus1_surveil_sends_top_card_to_graveyard_when_scripted_yes(self) -> None:
        """When the player chooses to put both library cards into the graveyard."""
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Put 3 cards in library so top 2 can be surveiled.
        lib_card_a = _make_creature("Card A", owner=p1)
        lib_card_b = _make_creature("Card B", owner=p1)
        lib_card_c = _make_creature("Card C", owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card_c)  # bottom
        p1.zones[Zone.LIBRARY].add(lib_card_b)  # middle
        p1.zones[Zone.LIBRARY].add(lib_card_a)  # top

        graveyard_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _activate_loyalty_ability(pw, 0, game)

        graveyard_after = len(p1.zones[Zone.GRAVEYARD].get_all())
        # Two yes answers → both top cards go to graveyard.
        assert graveyard_after == graveyard_before + 2

    def test_plus1_surveil_keeps_card_on_library_when_scripted_no(self) -> None:
        """When the player chooses NOT to put either card into the graveyard."""
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        lib_card_a = _make_creature("Card A", owner=p1)
        lib_card_b = _make_creature("Card B", owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card_b)  # bottom
        p1.zones[Zone.LIBRARY].add(lib_card_a)  # top

        lib_count_before = len(p1.zones[Zone.LIBRARY].get_all())
        gy_count_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _activate_loyalty_ability(pw, 0, game)

        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_count_before
        assert len(p1.zones[Zone.LIBRARY].get_all()) == lib_count_before

    def test_plus1_surveil_partial_send_to_graveyard(self) -> None:
        """When the player puts one of two cards into the graveyard."""
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        lib_card_a = _make_creature("Card A", owner=p1)
        lib_card_b = _make_creature("Card B", owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card_b)
        p1.zones[Zone.LIBRARY].add(lib_card_a)

        _activate_loyalty_ability(pw, 0, game)

        gy = p1.zones[Zone.GRAVEYARD].get_all()
        lib = p1.zones[Zone.LIBRARY].get_all()
        # Exactly one card should have moved to graveyard.
        assert len(gy) == 1
        assert len(lib) == 1

    def test_plus1_surveil_empty_library_does_not_raise(self) -> None:
        """With an empty library, the surveil no-ops gracefully."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Library already empty.
        _activate_loyalty_ability(pw, 0, game)
        assert pw.loyalty == 4  # Loyalty still updated.


# ---------------------------------------------------------------------------
# -1 ability: Discard
# ---------------------------------------------------------------------------


class TestRalZarekMinusOneAbility:
    """The -1 ability: any number of target players each discard a card."""

    def test_minus1_decreases_loyalty_from_3_to_2(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        assert pw.loyalty == 3
        _activate_loyalty_ability(pw, 1, game)
        assert pw.loyalty == 2

    def test_minus1_targeted_player_discards_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        hand_card = _make_creature("Hand Card", owner=p2)
        set_board_state(game, 1, hand=[hand_card])

        # Script: p2 chooses their hand card to discard.
        from engine.player import DeterministicPlayer
        if isinstance(p2, DeterministicPlayer):
            p2._script.append(hand_card)

        pw.chosen_targets = [p2]
        _activate_loyalty_ability(pw, 1, game)

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert p2.zones[Zone.GRAVEYARD].contains(hand_card)

    def test_minus1_with_no_targets_is_a_noop(self) -> None:
        """With no chosen targets, the -1 ability does not raise."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw.chosen_targets = []
        _activate_loyalty_ability(pw, 1, game)
        assert pw.loyalty == 2

    def test_minus1_multiple_players_each_discard(self) -> None:
        """Both players lose a card when both are targeted."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        card1 = _make_creature("P1 Card", owner=p1)
        card2 = _make_creature("P2 Card", owner=p2)
        set_board_state(game, 0, hand=[card1])
        set_board_state(game, 1, hand=[card2])

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(card1)
        if isinstance(p2, DeterministicPlayer):
            p2._script.append(card2)

        pw.chosen_targets = [p1, p2]
        _activate_loyalty_ability(pw, 1, game)

        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert len(p2.zones[Zone.HAND].get_all()) == 0


# ---------------------------------------------------------------------------
# -2 ability: Reanimate creature with mana value ≤ 3
# ---------------------------------------------------------------------------


class TestRalZarekMinusTwoAbility:
    """The -2 ability: return target creature card with mana value ≤3 from
    controller's graveyard to the battlefield."""

    def test_minus2_decreases_loyalty_from_3_to_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        assert pw.loyalty == 3
        _activate_loyalty_ability(pw, 2, game)
        assert pw.loyalty == 1

    def test_minus2_returns_mv3_creature_to_battlefield(self) -> None:
        """A creature with MV exactly 3 should be returned to the battlefield."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        # Creature with mana value 3 (generic 3)
        grave_creature = _make_creature("Graveyard Bear", cmc=3, owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[grave_creature])

        pw.chosen_targets = [grave_creature]
        _activate_loyalty_ability(pw, 2, game)

        assert p1.zones[Zone.BATTLEFIELD].contains(grave_creature)
        assert not p1.zones[Zone.GRAVEYARD].contains(grave_creature)

    def test_minus2_returns_mv1_creature_to_battlefield(self) -> None:
        """A creature with MV 1 (≤3) should be returned."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        cheap_creature = _make_creature("Cheap Bear", cmc=1, owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[cheap_creature])

        pw.chosen_targets = [cheap_creature]
        _activate_loyalty_ability(pw, 2, game)

        assert p1.zones[Zone.BATTLEFIELD].contains(cheap_creature)

    def test_minus2_does_not_return_mv4_creature(self) -> None:
        """A creature with MV 4 (> 3) must NOT be returned — the ability should
        only work on legal targets (MV ≤ 3).  If the card is set as the chosen
        target but fails the filter, it stays in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        big_creature = _make_creature("Big Creature", cmc=4, owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[big_creature])

        pw.chosen_targets = [big_creature]
        _activate_loyalty_ability(pw, 2, game)

        # Card must remain in graveyard (target was illegal).
        assert p1.zones[Zone.GRAVEYARD].contains(big_creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(big_creature)

    def test_minus2_does_not_return_mv5_creature(self) -> None:
        """A creature with MV 5 must NOT be returned."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        big_creature = _make_creature("Massive Creature", cmc=5, owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[big_creature])

        pw.chosen_targets = [big_creature]
        _activate_loyalty_ability(pw, 2, game)

        assert p1.zones[Zone.GRAVEYARD].contains(big_creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(big_creature)

    def test_minus2_with_no_target_does_not_raise(self) -> None:
        """With no chosen target, -2 resolves without crashing."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw.chosen_targets = []
        _activate_loyalty_ability(pw, 2, game)
        assert pw.loyalty == 1


# ---------------------------------------------------------------------------
# -7 ability: Coin-flip ultimatum
# ---------------------------------------------------------------------------


class TestRalZarekMinusSevenAbility:
    """The -7 ability: flip five coins; target opponent skips X turns
    where X = number of heads."""

    def test_minus7_correct_loyalty_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        ult = next(a for a in abilities if a.loyalty_cost == -7)
        assert ult.loyalty_cost == -7

    def test_minus7_loyalty_adjustment(self) -> None:
        """Verify loyalty change: starting at 3, after -7 = -4."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Inflate loyalty to allow the ability to "activate".
        pw.loyalty = 7  # ensure we can pay -7
        _activate_loyalty_ability(pw, 3, game)
        assert pw.loyalty == 0

    def test_minus7_all_heads_skips_five_turns(self) -> None:
        """If all 5 coins come up heads, the opponent skips 5 turns."""
        import unittest.mock as mock

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw.loyalty = 7

        pw.chosen_targets = [p2]
        # Patch random.random (or coin flip) to always return heads (1 / True).
        with mock.patch("random.random", return_value=0.0):  # < 0.5 → heads
            _activate_loyalty_ability(pw, 3, game)

        # Opponent should have 5 turns skipped queued.
        # Implementation may store skipped turns in extra_turns, a skip_turns
        # counter, or similar engine attribute.
        # We check at least one of the common patterns:
        turns_skipped = getattr(p2, "turns_to_skip", None)
        extra_turns_list = getattr(game, "extra_turns", [])
        # At least one observable change must reflect 5 turns skipped.
        # Accept either a dedicated skip counter or an empty extra_turns queue
        # (since "skip" ≠ "extra turn", a dedicated attribute is expected).
        assert turns_skipped is not None, (
            "p2 should have a 'turns_to_skip' attribute after -7 with 5 heads"
        )
        assert turns_skipped == 5

    def test_minus7_all_tails_skips_zero_turns(self) -> None:
        """If all 5 coins come up tails (X=0), the opponent skips 0 turns."""
        import unittest.mock as mock

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw.loyalty = 7

        pw.chosen_targets = [p2]
        # Patch so coins always return tails (0 heads).
        with mock.patch("random.random", return_value=1.0):  # >= 0.5 → tails
            _activate_loyalty_ability(pw, 3, game)

        turns_skipped = getattr(p2, "turns_to_skip", 0)
        assert turns_skipped == 0
