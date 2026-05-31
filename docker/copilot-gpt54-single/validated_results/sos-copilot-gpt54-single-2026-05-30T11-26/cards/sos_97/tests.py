"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import CardImpl, Creature, Planeswalker
from engine.types import Color, ManaCost, Phase, Step, Supertype
from test_utils import create_game, set_board_state


def _named_card(name: str) -> CardImpl:
    return CardImpl(name=name)


def _creature_card(name: str, mana_cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(mana_cost),
        base_power=2,
        base_toughness=2,
    )


def _ability(card: RalZarekGuestLecturer, loyalty_cost: int):
    for ability in card.get_loyalty_abilities():
        if ability.loyalty_cost == loyalty_cost:
            return ability
    raise AssertionError(f"Missing loyalty ability with cost {loyalty_cost}")


def _add_to_library(game, player, *cards) -> None:
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _end_turn(game) -> None:
    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.advance_phase()


class TestRalZarekGuestLecturerProperties:
    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name_and_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary_black_ral_with_three_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes
        assert card.colors == {Color.BLACK}
        assert card.starting_loyalty == 3
        assert card.loyalty == 3


class TestRalZarekGuestLecturerLoyaltyAbilities:
    def test_declares_four_loyalty_abilities_with_expected_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert [ability.loyalty_cost for ability in card.get_loyalty_abilities()] == [1, -1, -2, -7]


class TestRalZarekGuestLecturerPlusOne:
    def test_plus_one_surveils_two_and_moves_only_chosen_cards_to_graveyard(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = _named_card("Bottom Card")
        keep = _named_card("Keep Card")
        mill = _named_card("Mill Card")

        set_board_state(game, 0, battlefield=[ral])
        _add_to_library(game, p1, bottom, keep, mill)

        _ability(ral, 1).effect(game)

        assert game.get_graveyard(p1).contains(mill)
        assert not game.get_graveyard(p1).contains(keep)
        assert [card.name for card in game.get_library(p1).get_all()] == ["Bottom Card", "Keep Card"]

    def test_plus_one_handles_a_single_card_library(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        lone_card = _named_card("Only Card")

        set_board_state(game, 0, battlefield=[ral])
        _add_to_library(game, p1, lone_card)

        _ability(ral, 1).effect(game)

        assert game.get_graveyard(p1).contains(lone_card)
        assert game.get_library(p1).get_all() == []


class TestRalZarekGuestLecturerMinusOne:
    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        p1_discard = _named_card("P1 Discard")
        p1_keep = _named_card("P1 Keep")
        p2_discard = _named_card("P2 Discard")
        p2_keep = _named_card("P2 Keep")
        game = create_game(scripts=([p1_discard, p2_discard], [p2_discard]))
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[ral], hand=[p1_keep, p1_discard])
        set_board_state(game, 1, hand=[p2_keep, p2_discard])

        ral.chosen_targets = [p1, p2]
        ral._resolve_targets = [p1, p2]

        _ability(ral, -1).effect(game)

        assert game.get_graveyard(p1).contains(p1_discard)
        assert game.get_hand(p1).contains(p1_keep)
        assert game.get_graveyard(p2).contains(p2_discard)
        assert game.get_hand(p2).contains(p2_keep)

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = _named_card("P1 Card")
        p2_card = _named_card("P2 Card")

        set_board_state(game, 0, battlefield=[ral], hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])

        ral.chosen_targets = []
        ral._resolve_targets = []

        _ability(ral, -1).effect(game)

        assert game.get_hand(p1).contains(p1_card)
        assert game.get_hand(p2).contains(p2_card)
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_graveyard(p2).get_all() == []


class TestRalZarekGuestLecturerMinusTwo:
    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        cheap_creature = _creature_card("Cheap Ghoul", "{2}{B}")

        set_board_state(game, 0, battlefield=[ral], graveyard=[cheap_creature])

        ral.chosen_targets = [cheap_creature]
        ral._resolve_target = cheap_creature

        _ability(ral, -2).effect(game)

        assert game.get_battlefield(p1).contains(cheap_creature)
        assert not game.get_graveyard(p1).contains(cheap_creature)

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        expensive_creature = _creature_card("Expensive Demon", "{3}{B}")

        set_board_state(game, 0, battlefield=[ral], graveyard=[expensive_creature])

        ral.chosen_targets = [expensive_creature]
        ral._resolve_target = expensive_creature

        _ability(ral, -2).effect(game)

        assert game.get_graveyard(p1).contains(expensive_creature)
        assert not game.get_battlefield(p1).contains(expensive_creature)

    def test_minus_two_does_not_return_a_creature_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        opposing_creature = _creature_card("Opponent's Ghoul", "{2}{B}")

        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, graveyard=[opposing_creature])

        ral.chosen_targets = [opposing_creature]
        ral._resolve_target = opposing_creature

        _ability(ral, -2).effect(game)

        assert game.get_graveyard(p2).contains(opposing_creature)
        assert not game.get_battlefield(p1).contains(opposing_creature)
        assert not game.get_battlefield(p2).contains(opposing_creature)


class TestRalZarekGuestLecturerMinusSeven:
    def test_minus_seven_queues_target_opponents_next_turns_equal_to_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[ral])
        game.set_coin_flip_results([True, False, True, True, False])

        ral.chosen_targets = [p2]
        ral._resolve_target = p2

        _ability(ral, -7).effect(game)

        assert game.pending_skipped_turns == {1: 3}
        assert game.get_pending_skipped_turns(p2) == 3
        assert game.get_pending_skipped_turns(p1) == 0

    def test_minus_seven_with_zero_heads_queues_no_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[ral])
        game.set_coin_flip_results([False, False, False, False, False])

        ral.chosen_targets = [p2]
        ral._resolve_target = p2

        _ability(ral, -7).effect(game)

        assert game.pending_skipped_turns == {}
        assert game.get_pending_skipped_turns(p2) == 0

    def test_minus_seven_skipped_turns_are_consumed_when_that_opponents_turns_would_begin(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[ral])
        game.set_coin_flip_results([True, True, False, False, False])

        ral.chosen_targets = [p2]
        ral._resolve_target = p2

        _ability(ral, -7).effect(game)

        assert game.get_pending_skipped_turns(p2) == 2

        _end_turn(game)
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 1

        _end_turn(game)
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 0

        _end_turn(game)
        assert game.active_player is p2
