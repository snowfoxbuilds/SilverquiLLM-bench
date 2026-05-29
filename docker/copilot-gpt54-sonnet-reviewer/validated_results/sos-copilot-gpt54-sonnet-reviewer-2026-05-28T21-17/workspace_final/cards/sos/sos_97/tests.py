"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, Planeswalker, Sorcery
from engine.types import ManaCost, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _advance_to_next_turn(game) -> None:
    """Advance the game until the next turn begins."""
    starting_turn = game.turn_number
    while game.turn_number == starting_turn:
        game.advance_phase()


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the card spec."""

    def test_is_a_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name_and_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary_and_has_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes

    def test_starts_with_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Ral should expose the four printed loyalty abilities."""

    def test_declares_four_loyalty_abilities_with_expected_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]


class TestRalZarekGuestLecturerLoyaltyTargeting:
    """Public target declarations should match the printed loyalty text."""

    def test_minus_one_declares_any_number_of_target_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        requirements = walker.get_loyalty_target_requirements(game)
        assert len(requirements) == 4

        minus_one_requirements = requirements[1]
        assert len(minus_one_requirements) == 1

        req = minus_one_requirements[0]
        assert isinstance(req, TargetRequirement)
        assert req.zone == Zone.BATTLEFIELD
        assert req.min_targets == 0
        assert req.max_targets is None
        assert req.filter_fn(p1) is True
        assert req.filter_fn(p2) is True
        assert req.filter_fn(Creature(name="Not a player", base_power=2, base_toughness=2)) is False


class TestRalZarekGuestLecturerPlusOne:
    """+1 should surveil 2."""

    def test_plus_one_can_put_two_seen_cards_into_your_graveyard(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        top_card = Instant(
            name="Top Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{B}"),
        )
        next_card = Sorcery(
            name="Next Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        p1.zones[Zone.LIBRARY].add(next_card)
        p1.zones[Zone.LIBRARY].add(top_card)

        walker.get_loyalty_abilities()[0].effect(game)

        assert game.get_graveyard(p1).contains(top_card)
        assert game.get_graveyard(p1).contains(next_card)
        assert p1.zones[Zone.LIBRARY].contains(top_card) is False
        assert p1.zones[Zone.LIBRARY].contains(next_card) is False

    def test_plus_one_can_leave_seen_cards_in_your_library(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        top_card = Instant(
            name="Top Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{B}"),
        )
        next_card = Sorcery(
            name="Next Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        p1.zones[Zone.LIBRARY].add(next_card)
        p1.zones[Zone.LIBRARY].add(top_card)

        walker.get_loyalty_abilities()[0].effect(game)

        assert p1.zones[Zone.LIBRARY].contains(top_card) is True
        assert p1.zones[Zone.LIBRARY].contains(next_card) is True
        assert len(game.get_graveyard(p1).get_all()) == 0

    def test_plus_one_reorders_kept_cards_to_the_scripted_top_of_library_order(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        top_card = Instant(
            name="Top Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{B}"),
        )
        next_card = Sorcery(
            name="Next Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        p1.zones[Zone.LIBRARY].add(next_card)
        p1.zones[Zone.LIBRARY].add(top_card)
        p1._script.append(next_card)
        p1._script.append(top_card)

        walker.get_loyalty_abilities()[0].effect(game)

        assert p1.zones[Zone.LIBRARY].top(1) == [next_card]
        assert p1.zones[Zone.LIBRARY].top(2) == [top_card, next_card]
        assert len(game.get_graveyard(p1).get_all()) == 0


class TestRalZarekGuestLecturerMinusOne:
    """−1 should make each targeted player discard a card."""

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        first = Instant(name="Keep One", mana_cost=ManaCost.parse("{B}"))
        second = Instant(name="Keep Two", mana_cost=ManaCost.parse("{B}"))
        set_board_state(game, 0, hand=[first])
        set_board_state(game, 1, hand=[second])

        walker.get_loyalty_abilities()[1].effect(game)

        assert game.get_hand(p1).contains(first)
        assert game.get_hand(p2).contains(second)
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert len(game.get_graveyard(p2).get_all()) == 0

    def test_minus_one_makes_only_the_single_targeted_player_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        keep_mine = Instant(name="Keep Mine", mana_cost=ManaCost.parse("{B}"))
        discard_theirs = Sorcery(name="Discard Theirs", mana_cost=ManaCost.parse("{1}{B}"))
        keep_theirs = Instant(name="Keep Theirs", mana_cost=ManaCost.parse("{B}"))
        set_board_state(game, 0, hand=[keep_mine])
        set_board_state(game, 1, hand=[keep_theirs, discard_theirs])
        p2._script.append(discard_theirs)
        walker.chosen_targets = [p2]

        walker.get_loyalty_abilities()[1].effect(game)

        assert game.get_hand(p1).contains(keep_mine) is True
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert game.get_graveyard(p2).contains(discard_theirs)
        assert game.get_hand(p2).contains(keep_theirs)
        assert game.get_hand(p2).contains(discard_theirs) is False

    def test_minus_one_makes_each_targeted_player_discard_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        keep_mine = Instant(name="Keep Mine", mana_cost=ManaCost.parse("{B}"))
        discard_mine = Sorcery(name="Discard Mine", mana_cost=ManaCost.parse("{1}{B}"))
        keep_theirs = Instant(name="Keep Theirs", mana_cost=ManaCost.parse("{B}"))
        discard_theirs = Sorcery(
            name="Discard Theirs",
            mana_cost=ManaCost.parse("{1}{B}"),
        )
        set_board_state(game, 0, hand=[keep_mine, discard_mine])
        set_board_state(game, 1, hand=[keep_theirs, discard_theirs])
        p1._script.append(discard_mine)
        p2._script.append(discard_theirs)
        walker.chosen_targets = [p1, p2]

        walker.get_loyalty_abilities()[1].effect(game)

        assert game.get_graveyard(p1).contains(discard_mine)
        assert game.get_graveyard(p2).contains(discard_theirs)
        assert game.get_hand(p1).contains(keep_mine)
        assert game.get_hand(p2).contains(keep_theirs)
        assert game.get_hand(p1).contains(discard_mine) is False
        assert game.get_hand(p2).contains(discard_theirs) is False

    def test_minus_one_ignores_a_targeted_player_with_an_empty_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        discard_theirs = Instant(name="Only Card", mana_cost=ManaCost.parse("{B}"))
        set_board_state(game, 0, hand=[])
        set_board_state(game, 1, hand=[discard_theirs])
        p2._script.append(discard_theirs)
        walker.chosen_targets = [p1, p2]

        walker.get_loyalty_abilities()[1].effect(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert game.get_graveyard(p2).contains(discard_theirs)
        assert game.get_hand(p2).contains(discard_theirs) is False


class TestRalZarekGuestLecturerMinusTwo:
    """−2 should reanimate a small creature from your graveyard."""

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less_from_your_graveyard(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        apprentice = Creature(
            name="Apprentice of Night",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[apprentice])
        walker.chosen_targets = [apprentice]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_battlefield(p1).contains(apprentice) is True
        assert game.get_graveyard(p1).contains(apprentice) is False
        assert apprentice.controller is p1

    def test_minus_two_does_not_return_a_creature_with_mana_value_four_or_more(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        giant = Creature(
            name="Overbudget Giant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, graveyard=[giant])
        walker.chosen_targets = [giant]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_graveyard(p1).contains(giant) is True
        assert game.get_battlefield(p1).contains(giant) is False

    def test_minus_two_does_not_return_a_noncreature_card_even_if_its_mana_value_is_small(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        lesson = Sorcery(
            name="Dark Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{B}"),
        )
        set_board_state(game, 0, graveyard=[lesson])
        walker.chosen_targets = [lesson]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_graveyard(p1).contains(lesson) is True
        assert game.get_battlefield(p1).contains(lesson) is False


class TestRalZarekGuestLecturerMinusSeven:
    """−7 should count heads and skip that many of the target opponent's turns."""

    def test_minus_seven_uses_deterministic_coin_flips_to_set_skipped_turn_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p2]
        game.set_coin_flip_results([True, False, True, False, True])

        walker.get_loyalty_abilities()[3].effect(game)

        assert game.remaining_skipped_turns(p2) == 3
        assert game.remaining_skipped_turns(p1) == 0

    def test_minus_seven_makes_target_opponent_skip_their_next_x_turns(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p2]
        game.set_coin_flip_results([True, False, False, True, False])

        walker.get_loyalty_abilities()[3].effect(game)
        assert game.remaining_skipped_turns(p2) == 2

        _advance_to_next_turn(game)
        assert game.turn_number == 2
        assert game.active_player is p1
        assert game.remaining_skipped_turns(p2) == 1

        _advance_to_next_turn(game)
        assert game.turn_number == 3
        assert game.active_player is p1
        assert game.remaining_skipped_turns(p2) == 0

        _advance_to_next_turn(game)
        assert game.turn_number == 4
        assert game.active_player is p2
