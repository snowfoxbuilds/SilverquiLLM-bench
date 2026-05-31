"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _ability_with_cost(card: RalZarekGuestLecturer, cost: int) -> LoyaltyAbility:
    """Return the loyalty ability on *card* with the requested cost."""
    return next(ability for ability in card.get_loyalty_abilities() if ability.loyalty_cost == cost)


class TestRalZarekGuestLecturerProperties:
    """Static card data and loyalty declarations should match the SOS 97 spec."""

    def test_is_legendary_planeswalker_ral_with_expected_cost_loyalty_and_rules_text(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert card.rules_text == (
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads."
        )

    def test_exposes_surveil_metadata_for_the_plus_one_ability(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert "Surveil" in card.mechanic_keywords
        assert card.keyword_metadata["Surveil"]["amount"] == 2
        assert card.keyword_metadata["Surveil"]["ability_cost"] == +1

    def test_declares_four_loyalty_abilities_in_printed_order(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert all(isinstance(ability, LoyaltyAbility) for ability in abilities)
        assert [ability.loyalty_cost for ability in abilities] == [+1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "discard a card" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "Flip five coins" in abilities[3].description


class TestRalZarekGuestLecturerPlusOne:
    """The +1 loyalty ability should surveil 2."""

    def test_plus_one_moves_chosen_cards_from_the_top_two_into_your_graveyard(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        plus_one = _ability_with_cost(card, +1)

        bottom_card = Instant(name="Bottom Card")
        keep_card = Instant(name="Keep Card")
        mill_card = Instant(name="Mill Card")
        for obj in (bottom_card, keep_card, mill_card):
            obj.owner = p1
            obj.controller = p1
            p1.zones[Zone.LIBRARY].add(obj)

        plus_one.effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(mill_card)
        assert not p1.zones[Zone.GRAVEYARD].contains(keep_card)
        assert p1.zones[Zone.LIBRARY].contains(keep_card)
        assert p1.zones[Zone.LIBRARY].top(1)[0] is keep_card

    def test_plus_one_is_a_noop_with_an_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        _ability_with_cost(card, +1).effect(game)

        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0


class TestRalZarekGuestLecturerMinusOne:
    """The −1 loyalty ability should make each targeted player discard a card."""

    def test_each_targeted_player_discards_one_card(self) -> None:
        discard_a = Instant(name="Discard A")
        keep_a = Instant(name="Keep A")
        discard_b = Instant(name="Discard B")
        keep_b = Instant(name="Keep B")
        game = create_game(scripts=([discard_a], [discard_b]))
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_a, keep_a])
        set_board_state(game, 1, hand=[discard_b, keep_b])
        card.chosen_targets = [p1, p2]

        _ability_with_cost(card, -1).effect(game)

        assert game.get_graveyard(p1).contains(discard_a)
        assert game.get_hand(p1).contains(keep_a)
        assert game.get_graveyard(p2).contains(discard_b)
        assert game.get_hand(p2).contains(keep_b)

    def test_minus_one_allows_zero_targets_and_leaves_hands_unchanged(self) -> None:
        card_a = Instant(name="Card A")
        card_b = Instant(name="Card B")
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card_a])
        set_board_state(game, 1, hand=[card_b])
        card.chosen_targets = []

        _ability_with_cost(card, -1).effect(game)

        assert game.get_hand(p1).contains(card_a)
        assert game.get_hand(p2).contains(card_b)
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert len(game.get_graveyard(p2).get_all()) == 0


class TestRalZarekGuestLecturerMinusTwo:
    """The −2 loyalty ability should reanimate a small creature from your graveyard."""

    def test_returns_target_creature_card_with_mana_value_three_or_less_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        small_creature = Creature(
            name="Reassembled Assistant",
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=3,
            base_toughness=1,
        )
        set_board_state(game, 0, graveyard=[small_creature])
        card.chosen_targets = [small_creature]

        _ability_with_cost(card, -2).effect(game)

        assert game.get_battlefield(p1).contains(small_creature)
        assert not game.get_graveyard(p1).contains(small_creature)

    def test_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        expensive_creature = Creature(
            name="Too Expensive",
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, graveyard=[expensive_creature])
        card.chosen_targets = [expensive_creature]

        _ability_with_cost(card, -2).effect(game)

        assert game.get_graveyard(p1).contains(expensive_creature)
        assert not game.get_battlefield(p1).contains(expensive_creature)


class TestRalZarekGuestLecturerMinusSeven:
    """The −7 loyalty ability should flip five coins and skip turns equal to heads."""

    def test_minus_seven_counts_scripted_heads_and_schedules_that_many_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flip_results([True, False, True, False, True])

        _ability_with_cost(card, -7).effect(game)

        assert card.last_coin_flip_results == [True, False, True, False, True]
        assert card.last_coin_flip_heads == 3
        assert game.last_coin_flip_results == [True, False, True, False, True]
        assert game.get_scheduled_skipped_turns(p2) == 3

    def test_minus_seven_with_zero_heads_does_not_schedule_any_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flip_results([False, False, False, False, False])

        _ability_with_cost(card, -7).effect(game)

        assert card.last_coin_flip_results == [False, False, False, False, False]
        assert card.last_coin_flip_heads == 0
        assert game.get_scheduled_skipped_turns(p2) == 0

    def test_minus_seven_skips_the_target_opponents_next_turns_and_consumes_the_schedule(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flip_results([True, True, False, False, False])

        _ability_with_cost(card, -7).effect(game)

        assert game.get_scheduled_skipped_turns(p2) == 2

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_scheduled_skipped_turns(p2) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_scheduled_skipped_turns(p2) == 0

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p2
