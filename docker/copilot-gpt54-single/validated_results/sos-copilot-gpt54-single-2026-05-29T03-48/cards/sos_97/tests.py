"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability
from engine.card import Creature, Instant, Planeswalker
from engine.casting import resolve_top
from engine.turn import run_turn
from engine.types import ManaCost, Phase, Supertype
from test_utils import create_game, set_board_state


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _loyalty_instance(card: RalZarekGuestLecturer, index: int) -> LoyaltyAbilityInstance:
    printed = card.get_loyalty_abilities()[index]
    return LoyaltyAbilityInstance(
        source=card,
        controller=card.controller,
        loyalty_cost=printed.loyalty_cost,
        effect=printed.effect,
        description=printed.description,
    )


def _test_creature(name: str, cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=2,
        base_toughness=2,
    )


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_legendary_ral_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_mana_cost_and_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_has_four_loyalty_abilities_with_printed_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Loyalty abilities should match the printed SOS 97 behavior."""

    def test_plus_one_surveils_two_and_adds_loyalty(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = Instant(name="Bottom Card")
        keep = Instant(name="Keep Card")
        mill = Instant(name="Mill Card")

        set_board_state(game, 0, battlefield=[card])
        library = game.get_library(p1)
        library.add(bottom)
        library.add(keep)
        library.add(mill)
        _set_precombat_main(game)

        activate_ability(game, p1, _loyalty_instance(card, 0))

        assert card.loyalty == 4
        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_graveyard(p1).contains(mill)
        assert not game.get_graveyard(p1).contains(keep)
        assert library.get_all() == [bottom, keep]

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        first = Instant(name="First Card")
        second = Instant(name="Second Card")

        set_board_state(game, 0, battlefield=[card], hand=[first])
        set_board_state(game, 1, hand=[second])
        card.chosen_targets = []

        def _unexpected_choose_card(_cards: object, _description: str) -> object:
            raise AssertionError("discard selection should not be requested with zero targets")

        p1.choose_card = _unexpected_choose_card  # type: ignore[method-assign]
        p2.choose_card = _unexpected_choose_card  # type: ignore[method-assign]

        card.get_loyalty_abilities()[1].effect(game)

        assert game.get_hand(p1).contains(first)
        assert game.get_hand(p2).contains(second)

    def test_minus_one_makes_each_chosen_player_discard_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        first = Instant(name="First Card")
        second = Instant(name="Second Card")

        set_board_state(game, 0, battlefield=[card], hand=[first])
        set_board_state(game, 1, hand=[second])
        card.chosen_targets = [p1, p2]
        p1.choose_card = lambda cards, _description: cards[0]  # type: ignore[method-assign]
        p2.choose_card = lambda cards, _description: cards[0]  # type: ignore[method-assign]

        card.get_loyalty_abilities()[1].effect(game)

        assert game.get_graveyard(p1).contains(first)
        assert game.get_graveyard(p2).contains(second)
        assert not game.get_hand(p1).contains(first)
        assert not game.get_hand(p2).contains(second)

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _test_creature("Campus Recluse", "{2}{B}")

        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target

        card.get_loyalty_abilities()[2].effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)

    def test_minus_two_leaves_mana_value_four_target_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _test_creature("Too Expensive", "{3}{B}")

        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target

        card.get_loyalty_abilities()[2].effect(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_battlefield(p1).contains(target)

    def test_minus_seven_flips_five_scripted_coins_and_schedules_matching_skips(self) -> None:
        game = create_game(coin_flips=[True, False, True, True, False])
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7

        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        _set_precombat_main(game)

        activate_ability(game, p1, _loyalty_instance(card, 3))

        assert card.loyalty == 0
        assert len(game.stack) == 1

        resolve_top(game)

        assert game.coin_flip_history == [True, False, True, True, False]
        assert card.last_coin_flip_results == [True, False, True, True, False]
        assert card.last_coin_flip_heads == 3
        assert game.remaining_skipped_turns(p2) == 3

    def test_minus_seven_makes_target_opponent_skip_next_x_turns(self) -> None:
        game = create_game(coin_flips=[True, False, True, False, False])
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7

        set_board_state(game, 0, battlefield=[card])
        card.chosen_targets = [p2]
        _set_precombat_main(game)

        activate_ability(game, p1, _loyalty_instance(card, 3))
        resolve_top(game)

        assert game.remaining_skipped_turns(p2) == 2

        run_turn(game)

        assert game.turn_number == 2
        assert game.active_player is p1
        assert game.remaining_skipped_turns(p2) == 1

        run_turn(game)

        assert game.turn_number == 3
        assert game.active_player is p1
        assert game.remaining_skipped_turns(p2) == 0

        run_turn(game)

        assert game.turn_number == 4
        assert game.active_player is p2
