"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from benchmarks.sos.workspace.engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Planeswalker
from benchmarks.sos.workspace.engine.types import ManaCost, Phase, Step, Supertype
from benchmarks.sos.workspace.tests.test_utils import advance_to_phase, create_game, set_board_state


def _activate_loyalty(
    game: object,
    card: RalZarekGuestLecturer,
    ability_index: int,
    *,
    targets: list[object] | None = None,
) -> None:
    loyalty_ability = card.get_loyalty_abilities()[ability_index]
    activate_ability(
        game,
        card.controller,
        LoyaltyAbilityInstance(
            source=card,
            controller=card.controller,
            loyalty_cost=loyalty_ability.loyalty_cost,
            effect=loyalty_ability.effect,
            description=loyalty_ability.description,
            targets=[] if targets is None else list(targets),
        ),
    )


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_legendary_ral_planeswalker_with_three_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_name_and_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_exposes_four_loyalty_abilities_with_the_printed_costs(self) -> None:
        costs = [ability.loyalty_cost for ability in RalZarekGuestLecturer(owner=None).get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestRalZarekGuestLecturerAbilities:
    """Ral's testable loyalty abilities should match the spec."""

    def test_plus_one_surveils_two(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([True, False])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 0)

        assert card.loyalty == 4
        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_library(p1).get_all() == [bottom, middle]

    def test_minus_one_allows_targeting_any_number_of_players_and_each_target_discards_a_card(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, p2 = game.players
        self_card = CardImpl(name="Self Discard", owner=p1, controller=p1)
        opponent_card = CardImpl(name="Opponent Discard", owner=p2, controller=p2)
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=[self_card])
        set_board_state(game, 1, hand=[opponent_card])
        p1._script.append(self_card)
        p2._script.append(opponent_card)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 1, targets=[p1, p2])

        assert card.loyalty == 2
        resolve_top(game)

        assert game.get_graveyard(p1).contains(self_card)
        assert game.get_graveyard(p2).contains(opponent_card)
        assert game.get_hand(p1).get_all() == []
        assert game.get_hand(p2).get_all() == []

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, p2 = game.players
        self_card = CardImpl(name="Kept Self Card", owner=p1, controller=p1)
        opponent_card = CardImpl(name="Kept Opponent Card", owner=p2, controller=p2)
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=[self_card])
        set_board_state(game, 1, hand=[opponent_card])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 1, targets=[])

        assert card.loyalty == 2
        resolve_top(game)

        assert game.get_hand(p1).get_all() == [self_card]
        assert game.get_hand(p2).get_all() == [opponent_card]

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less_from_your_graveyard_to_the_battlefield(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1 = game.players[0]
        returned = Creature(
            name="Returned Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=3,
            base_toughness=2,
        )
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[returned])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 2, targets=[returned])

        assert card.loyalty == 1
        resolve_top(game)

        assert game.get_battlefield(p1).contains(returned)
        assert not game.get_graveyard(p1).contains(returned)

    def test_minus_two_does_not_return_a_target_with_mana_value_greater_than_three(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1 = game.players[0]
        too_expensive = Creature(
            name="Expensive Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[too_expensive])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 2, targets=[too_expensive])

        resolve_top(game)

        assert game.get_graveyard(p1).contains(too_expensive)
        assert not game.get_battlefield(p1).contains(too_expensive)

    def test_minus_seven_flips_five_coins_and_target_opponent_skips_that_many_next_turns(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7
        set_board_state(game, 0, battlefield=[card])
        game.queue_coin_flips(True, False, True, False, True)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 3, targets=[p2])

        assert card.loyalty == 0
        resolve_top(game)

        assert game.coin_flip_history == [True, False, True, False, True]
        assert game.get_skipped_turns(p2) == 3

        for remaining_skips in [2, 1, 0]:
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()

            assert game.active_player is p1
            assert (game.phase, game.step) == (Phase.BEGINNING, Step.UNTAP)
            assert game.get_skipped_turns(p2) == remaining_skips

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()

        assert game.active_player is p2
        assert (game.phase, game.step) == (Phase.BEGINNING, Step.UNTAP)

    def test_minus_seven_with_zero_heads_does_not_make_the_target_skip_a_turn(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7
        set_board_state(game, 0, battlefield=[card])
        game.queue_coin_flips(False, False, False, False, False)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        _activate_loyalty(game, card, 3, targets=[p2])

        assert card.loyalty == 0
        resolve_top(game)

        assert game.coin_flip_history == [False, False, False, False, False]
        assert game.get_skipped_turns(p2) == 0

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()

        assert game.active_player is p2
        assert (game.phase, game.step) == (Phase.BEGINNING, Step.UNTAP)
