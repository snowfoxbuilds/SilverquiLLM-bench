"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability
from engine.card import CardImpl, Creature, Planeswalker
from engine.game import pending_skipped_turns, set_coin_flip_results
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_a_legendary_ral_planeswalker_with_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_mana_cost_is_one_black_black(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Ral should expose the four loyalty abilities from the spec."""

    def test_declares_four_loyalty_abilities_with_expected_costs(self) -> None:
        costs = [ability.loyalty_cost for ability in RalZarekGuestLecturer(owner=None).get_loyalty_abilities()]

        assert costs == [1, -1, -2, -7]


class TestRalZarekGuestLecturerPlusOne:
    """The +1 ability should surveil 2."""

    def test_plus_one_surveils_two_cards_from_the_top_of_your_library(self) -> None:
        game = create_game()
        controller = game.players[0]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[0]

        bottom = CardImpl(name="Bottom Lesson")
        middle = CardImpl(name="Middle Lesson")
        top = CardImpl(name="Top Lesson")
        library = controller.zones[Zone.LIBRARY]
        library.add(bottom)
        library.add(middle)
        library.add(top)

        decisions = iter([True, False])
        controller.choose_yes_no = lambda prompt: next(decisions)

        ability.effect(game)

        assert controller.zones[Zone.GRAVEYARD].contains(top)
        assert not controller.zones[Zone.GRAVEYARD].contains(middle)
        assert library.contains(bottom)
        assert library.contains(middle)
        assert not library.contains(top)


class TestRalZarekGuestLecturerMinusOne:
    """The −1 ability should make each targeted player discard a card."""

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[1]

        controller_card = CardImpl(name="Controller Note")
        opponent_card = CardImpl(name="Opponent Note")
        set_board_state(game, 0, hand=[controller_card])
        set_board_state(game, 1, hand=[opponent_card])

        walker.chosen_targets = []
        walker._resolve_targets = []
        ability.effect(game)

        assert controller.zones[Zone.HAND].contains(controller_card)
        assert opponent.zones[Zone.HAND].contains(opponent_card)
        assert not controller.zones[Zone.GRAVEYARD].contains(controller_card)
        assert not opponent.zones[Zone.GRAVEYARD].contains(opponent_card)

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[1]

        controller_card = CardImpl(name="Controller Note")
        opponent_card = CardImpl(name="Opponent Note")
        set_board_state(game, 0, hand=[controller_card])
        set_board_state(game, 1, hand=[opponent_card])

        controller.choose_card = lambda cards, description: controller_card
        opponent.choose_card = lambda cards, description: opponent_card
        walker.chosen_targets = [controller, opponent]
        walker._resolve_targets = [controller, opponent]
        ability.effect(game)

        assert not controller.zones[Zone.HAND].contains(controller_card)
        assert not opponent.zones[Zone.HAND].contains(opponent_card)
        assert controller.zones[Zone.GRAVEYARD].contains(controller_card)
        assert opponent.zones[Zone.GRAVEYARD].contains(opponent_card)


class TestRalZarekGuestLecturerMinusTwo:
    """The −2 ability should reanimate a small creature from your graveyard."""

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        controller = game.players[0]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[2]

        target = Creature(
            name="Returned Assistant",
            mana_cost=ManaCost.parse("{2}{B}"),
            owner=controller,
            controller=controller,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[target])

        walker.chosen_targets = [target]
        walker._resolve_target = target
        ability.effect(game)

        assert controller.zones[Zone.BATTLEFIELD].contains(target)
        assert not controller.zones[Zone.GRAVEYARD].contains(target)

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = create_game()
        controller = game.players[0]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[2]

        target = Creature(
            name="Too Expensive Assistant",
            mana_cost=ManaCost.parse("{3}{B}"),
            owner=controller,
            controller=controller,
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, graveyard=[target])

        walker.chosen_targets = [target]
        walker._resolve_target = target
        ability.effect(game)

        assert controller.zones[Zone.GRAVEYARD].contains(target)
        assert not controller.zones[Zone.BATTLEFIELD].contains(target)

    def test_minus_two_does_not_return_a_card_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        ability = walker.get_loyalty_abilities()[2]

        target = Creature(
            name="Opposing Assistant",
            mana_cost=ManaCost.parse("{2}{B}"),
            owner=opponent,
            controller=opponent,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, graveyard=[target])

        walker.chosen_targets = [target]
        walker._resolve_target = target
        ability.effect(game)

        assert opponent.zones[Zone.GRAVEYARD].contains(target)
        assert not controller.zones[Zone.BATTLEFIELD].contains(target)


class TestRalZarekGuestLecturerTargeting:
    """Previously untestable loyalty targeting restrictions."""

    def test_minus_one_loyalty_targeting_only_allows_players(self) -> None:
        game = create_game()
        controller = game.players[0]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        requirement = walker.get_loyalty_targets(game, 1)[0]
        non_player = Creature(name="Lecture Bear", base_power=2, base_toughness=2)

        assert requirement.filter_fn(controller) is True
        assert requirement.filter_fn(game.players[1]) is True
        assert requirement.filter_fn(non_player) is False

    def test_minus_seven_declare_loyalty_targets_rejects_targeting_yourself(self) -> None:
        game = create_game()
        controller = game.players[0]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)

        controller.choose_target = lambda options, requirement: controller

        with pytest.raises(ValueError, match="Chosen loyalty target does not satisfy filter"):
            walker.declare_loyalty_targets(game, 3, player=controller)


class TestRalZarekGuestLecturerMinusSeven:
    """The −7 ability should flip coins and schedule skipped turns."""

    @staticmethod
    def _activate_minus_seven(game, walker, controller):
        ability = walker.get_loyalty_abilities()[3]
        activate_ability(
            game,
            controller,
            LoyaltyAbilityInstance(
                source=walker,
                controller=controller,
                loyalty_cost=ability.loyalty_cost,
                effect=ability.effect,
                description=ability.description,
                ability_index=3,
            ),
        )
        return game.stack.pop()

    def test_minus_seven_flips_five_coins_and_schedules_skips_equal_to_heads(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        walker.loyalty = 7
        set_board_state(game, 0, battlefield=[walker])
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        controller.choose_target = lambda options, requirement: opponent
        set_coin_flip_results(game, [True, False, True, True, False])

        stack_obj = self._activate_minus_seven(game, walker, controller)
        stack_obj.on_resolve(game)

        assert [record.result for record in game.coin_flip_history] == [True, False, True, True, False]
        assert all(record.player is controller for record in game.coin_flip_history)
        assert all(record.source is walker for record in game.coin_flip_history)
        assert pending_skipped_turns(game, opponent) == 3
        assert pending_skipped_turns(game, controller) == 0

    def test_minus_seven_with_zero_heads_schedules_no_skipped_turns(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        walker = RalZarekGuestLecturer(owner=controller, controller=controller)
        walker.loyalty = 7
        set_board_state(game, 0, battlefield=[walker])
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        controller.choose_target = lambda options, requirement: opponent
        set_coin_flip_results(game, [False, False, False, False, False])

        stack_obj = self._activate_minus_seven(game, walker, controller)
        stack_obj.on_resolve(game)

        assert [record.result for record in game.coin_flip_history] == [False, False, False, False, False]
        assert pending_skipped_turns(game, opponent) == 0
