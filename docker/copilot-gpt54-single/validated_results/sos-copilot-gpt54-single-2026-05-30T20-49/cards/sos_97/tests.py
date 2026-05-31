"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Planeswalker
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _main_phase_game():
    clear_loyalty_tracking()
    game = create_game()
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return game


def _load_library(player, cards) -> None:
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _activate_and_resolve_loyalty_ability(
    game,
    player,
    planeswalker: RalZarekGuestLecturer,
    ability_index: int,
) -> None:
    ability = planeswalker.get_loyalty_abilities()[ability_index]
    activate_ability(
        game,
        player,
        LoyaltyAbilityInstance(
            source=planeswalker,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    assert stack_obj.source is planeswalker
    stack_obj.on_resolve(game)


def _advance_to_next_turn(game) -> None:
    current_turn = game.turn_number
    while game.turn_number == current_turn:
        game.advance_phase()


class TestRalZarekGuestLecturerProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_legendary_planeswalker_ral_with_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """The planeswalker should declare the printed four loyalty abilities."""

    def test_declares_four_loyalty_abilities_with_printed_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "discard a card" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "Flip five coins" in abilities[3].description


class TestRalZarekGuestLecturerPlusOne:
    """+1 should surveil 2."""

    def test_plus_one_surveille_s_two_cards_and_keeps_unchosen_card_in_library(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = Creature(name="Bottom Card", base_power=1, base_toughness=1)
        keep = Creature(name="Keep Me", base_power=1, base_toughness=1)
        put_in_graveyard = Creature(name="Bin Me", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[walker])
        _load_library(p1, [bottom, keep, put_in_graveyard])
        p1.choose_yes_no = lambda prompt: "Bin Me" in prompt

        _activate_and_resolve_loyalty_ability(game, p1, walker, 0)

        assert walker.loyalty == 4
        assert game.get_graveyard(p1).contains(put_in_graveyard)
        assert not game.get_graveyard(p1).contains(keep)
        assert game.get_library(p1).contains(bottom)
        assert game.get_library(p1).contains(keep)
        assert not game.get_library(p1).contains(put_in_graveyard)
        assert game.get_library(p1).top(1)[0] is keep

    def test_plus_one_lets_you_choose_the_final_order_of_kept_cards(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = Creature(name="Bottom Card", base_power=1, base_toughness=1)
        lower = Creature(name="Lower Card", base_power=1, base_toughness=1)
        upper = Creature(name="Upper Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[walker])
        _load_library(p1, [bottom, lower, upper])
        p1.choose_yes_no = lambda prompt: False
        p1.choose_order = lambda items, description: [upper, lower]

        _activate_and_resolve_loyalty_ability(game, p1, walker, 0)

        assert walker.loyalty == 4
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert game.get_library(p1).top(2) == [upper, lower]


class TestRalZarekGuestLecturerMinusOne:
    """-1 should make each chosen player discard a card."""

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        your_keep = Creature(name="Your Keep", base_power=1, base_toughness=1)
        your_discard = Creature(name="Your Discard", base_power=1, base_toughness=1)
        opp_keep = Creature(name="Opp Keep", base_power=1, base_toughness=1)
        opp_discard = Creature(name="Opp Discard", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[walker], hand=[your_keep, your_discard])
        set_board_state(game, 1, hand=[opp_keep, opp_discard])
        walker.chosen_targets = [p1, p2]
        p1.choose_card = lambda cards, description: your_discard
        p2.choose_card = lambda cards, description: opp_discard

        _activate_and_resolve_loyalty_ability(game, p1, walker, 1)

        assert walker.loyalty == 2
        assert game.get_graveyard(p1).contains(your_discard)
        assert game.get_graveyard(p2).contains(opp_discard)
        assert game.get_hand(p1).contains(your_keep)
        assert game.get_hand(p2).contains(opp_keep)
        assert not game.get_hand(p1).contains(your_discard)
        assert not game.get_hand(p2).contains(opp_discard)

    def test_minus_one_with_no_targets_discards_nothing(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        your_card = Creature(name="Your Card", base_power=1, base_toughness=1)
        opp_card = Creature(name="Opp Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[walker], hand=[your_card])
        set_board_state(game, 1, hand=[opp_card])
        walker.chosen_targets = []

        _activate_and_resolve_loyalty_ability(game, p1, walker, 1)

        assert walker.loyalty == 2
        assert game.get_hand(p1).contains(your_card)
        assert game.get_hand(p2).contains(opp_card)
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert len(game.get_graveyard(p2).get_all()) == 0


class TestRalZarekGuestLecturerMinusTwo:
    """-2 should reanimate only a qualifying creature card from your graveyard."""

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        small_creature = Creature(
            name="Returned Bear",
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=3,
            base_toughness=3,
        )
        large_creature = Creature(
            name="Still Dead",
            mana_cost=ManaCost.parse("{4}{B}"),
            base_power=5,
            base_toughness=5,
        )

        set_board_state(game, 0, battlefield=[walker], graveyard=[small_creature, large_creature])
        walker.chosen_targets = [small_creature]

        _activate_and_resolve_loyalty_ability(game, p1, walker, 2)

        assert walker.loyalty == 1
        assert game.get_battlefield(p1).contains(small_creature)
        assert not game.get_graveyard(p1).contains(small_creature)
        assert game.get_graveyard(p1).contains(large_creature)

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        large_creature = Creature(
            name="Too Expensive",
            mana_cost=ManaCost.parse("{4}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, battlefield=[walker], graveyard=[large_creature])
        walker.chosen_targets = [large_creature]

        _activate_and_resolve_loyalty_ability(game, p1, walker, 2)

        assert walker.loyalty == 1
        assert game.get_graveyard(p1).contains(large_creature)
        assert not game.get_battlefield(p1).contains(large_creature)


class TestRalZarekGuestLecturerMinusSeven:
    """-7 should flip five coins and skip the targeted opponent's next X turns."""

    def test_minus_seven_schedules_skipped_turns_equal_to_scripted_heads(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.loyalty = 7

        set_board_state(game, 0, battlefield=[walker])
        walker.chosen_targets = [p2]
        game.set_coin_flip_results([True, False, True, True, False])

        _activate_and_resolve_loyalty_ability(game, p1, walker, 3)

        assert walker.loyalty == 0
        assert game.coin_flip_history == [True, False, True, True, False]
        assert game.get_skipped_turns_remaining(p2) == 3
        assert game.get_skipped_turns_remaining(p1) == 0

    def test_minus_seven_causes_target_opponent_to_skip_that_many_upcoming_turns(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        p2 = game.players[1]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.loyalty = 7

        set_board_state(game, 0, battlefield=[walker])
        walker.chosen_targets = [p2]
        game.set_coin_flip_results([True, True, False, False, False])

        _activate_and_resolve_loyalty_ability(game, p1, walker, 3)

        _advance_to_next_turn(game)
        assert game.turn_number == 2
        assert game.active_player is p1
        assert game.get_skipped_turns_remaining(p2) == 1

        _advance_to_next_turn(game)
        assert game.turn_number == 3
        assert game.active_player is p1
        assert game.get_skipped_turns_remaining(p2) == 0

        _advance_to_next_turn(game)
        assert game.turn_number == 4
        assert game.active_player is p2
