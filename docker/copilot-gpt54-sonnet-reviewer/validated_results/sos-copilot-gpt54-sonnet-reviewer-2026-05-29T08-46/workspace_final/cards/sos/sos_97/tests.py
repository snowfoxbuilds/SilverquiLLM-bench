"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import card_colors, create_game, set_board_state


def _creature_card(name: str, cost: str, owner) -> Creature:
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        mana_cost=ManaCost.parse(cost),
        base_power=2,
        base_toughness=2,
    )


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_legendary_planeswalker_with_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_name_mana_cost_starting_loyalty_and_color(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert card_colors(card) == {"B"}


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """The card should declare the four printed loyalty abilities."""

    def test_declares_four_loyalty_abilities_in_oracle_order(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]

    def test_minus_one_advertises_zero_to_many_player_targets(self) -> None:
        game = create_game()
        ability = RalZarekGuestLecturer(owner=game.players[0], controller=game.players[0]).get_loyalty_abilities()[1]

        assert ability.target_type == "player"
        assert ability.min_targets == 0
        assert ability.max_targets is None
        assert ability.allows_target_count(0) is True
        assert ability.allows_target_count(1) is True
        assert ability.allows_target_count(2) is True
        assert ability.allows_target_count(3) is True
        assert ability.get_legal_targets(game) == game.players


class TestRalZarekGuestLecturerPlusOne:
    """+1: Surveil 2."""

    def test_plus_one_surveilles_two_cards(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = _creature_card("Bottom Card", "{B}", p1)
        next_card = _creature_card("Second Card", "{1}{B}", p1)
        top = _creature_card("Top Card", "{2}{B}", p1)

        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(next_card)
        p1.zones[Zone.LIBRARY].add(top)

        walker.get_loyalty_abilities()[0].effect(game)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_graveyard(p1).contains(next_card)
        assert p1.zones[Zone.LIBRARY].contains(bottom)
        assert not p1.zones[Zone.LIBRARY].contains(top)
        assert not p1.zones[Zone.LIBRARY].contains(next_card)


class TestRalZarekGuestLecturerMinusOne:
    """−1: Any number of target players each discard a card."""

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = _creature_card("P1 Hand Card", "{B}", p1)
        p2_card = _creature_card("P2 Hand Card", "{B}", p2)

        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        walker.chosen_targets = []

        walker.get_loyalty_abilities()[1].effect(game)

        assert game.get_hand(p1).contains(p1_card)
        assert game.get_hand(p2).contains(p2_card)
        assert not game.get_graveyard(p1).contains(p1_card)
        assert not game.get_graveyard(p2).contains(p2_card)

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = _creature_card("P1 Hand Card", "{B}", p1)
        p2_card = _creature_card("P2 Hand Card", "{B}", p2)

        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        p1.choose_card = lambda cards, description: cards[0]
        p2.choose_card = lambda cards, description: cards[0]
        walker.chosen_targets = [p1, p2]

        walker.get_loyalty_abilities()[1].effect(game)

        assert game.get_graveyard(p1).contains(p1_card)
        assert game.get_graveyard(p2).contains(p2_card)
        assert not game.get_hand(p1).contains(p1_card)
        assert not game.get_hand(p2).contains(p2_card)


class TestRalZarekGuestLecturerMinusTwo:
    """−2: Reanimate a small creature from your graveyard."""

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Returned Apprentice", "{2}{B}", p1)

        set_board_state(game, 0, graveyard=[target])
        walker.chosen_targets = [target]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)

    def test_minus_two_does_not_return_creature_card_with_mana_value_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Too Expensive", "{3}{B}", p1)

        set_board_state(game, 0, graveyard=[target])
        walker.chosen_targets = [target]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_battlefield(p1).contains(target)

    def test_minus_two_does_not_return_creature_card_from_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Opponents Creature", "{2}{B}", p2)

        set_board_state(game, 1, graveyard=[target])
        walker.chosen_targets = [target]

        walker.get_loyalty_abilities()[2].effect(game)

        assert game.get_graveyard(p2).contains(target)
        assert not game.get_battlefield(p1).contains(target)
        assert not game.get_battlefield(p2).contains(target)


class TestRalZarekGuestLecturerMinusSeven:
    """−7: Flip five coins; target opponent skips turns equal to heads."""

    def test_minus_seven_advertises_single_opponent_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ability = RalZarekGuestLecturer(owner=p1, controller=p1).get_loyalty_abilities()[3]

        assert ability.target_type == "opponent"
        assert ability.min_targets == 1
        assert ability.max_targets == 1
        assert ability.allows_target_count(0) is False
        assert ability.allows_target_count(1) is True
        assert ability.allows_target_count(2) is False
        assert ability.get_legal_targets(game) == [p2]

    def test_minus_seven_flips_five_coins_and_sets_skipped_turn_count_from_heads(self) -> None:
        game = create_game(scripts=([True, False, True, False, True], []))
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p2]

        walker.get_loyalty_abilities()[3].effect(game)

        assert walker.last_coin_flip_results == [True, False, True, False, True]
        assert walker.last_skipped_turns == 3
        assert game.coin_flip_history == [True, False, True, False, True]
        assert game.get_pending_skipped_turns(p2) == 3

    def test_minus_seven_skipped_turns_are_consumed_during_turn_rotation(self) -> None:
        game = create_game(scripts=([True, True, False, False, False], []))
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p2]

        walker.get_loyalty_abilities()[3].effect(game)

        assert game.get_pending_skipped_turns(p2) == 2

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 0

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p2
