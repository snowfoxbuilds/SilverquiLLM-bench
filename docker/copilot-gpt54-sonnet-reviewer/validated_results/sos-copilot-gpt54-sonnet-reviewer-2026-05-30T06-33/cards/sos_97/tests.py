"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import activate_ability
from engine.card import CardImpl, Creature, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state

ORACLE_TEXT = (
    "+1: Surveil 2.\n"
    "−1: Any number of target players each discard a card.\n"
    "−2: Return target creature card with mana value 3 or less from your "
    "graveyard to the battlefield.\n"
    "−7: Flip five coins. Target opponent skips their next X turns, where X "
    "is the number of coins that came up heads."
)


class TestRalZarekGuestLecturerProperties:
    """Static card data and loyalty declaration should match the spec."""

    def test_is_legendary_planeswalker_with_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_name_mana_cost_rules_text_and_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.rules_text == ORACLE_TEXT
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_declares_four_loyalty_abilities_with_expected_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]


class TestRalZarekGuestLecturerAbilities:
    """Each loyalty ability should produce its observable card-specific effect."""

    def test_plus_one_surveils_two_cards(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        bottom = CardImpl(name="Bottom Lesson")
        second = CardImpl(name="Second Lesson")
        top = CardImpl(name="Top Lesson")
        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(second)
        p1.zones[Zone.LIBRARY].add(top)

        walker.get_loyalty_abilities()[0].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert not p1.zones[Zone.LIBRARY].contains(top)
        assert p1.zones[Zone.LIBRARY].contains(second)
        assert p1.zones[Zone.LIBRARY].contains(bottom)
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 1
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 2

    def test_plus_one_records_exact_order_of_kept_surveilled_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        bottom = CardImpl(name="Bottom Lesson")
        second = CardImpl(name="Second Lesson")
        top = CardImpl(name="Top Lesson")
        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(second)
        p1.zones[Zone.LIBRARY].add(top)
        p1._script.extend([False, False, second])

        walker.get_loyalty_abilities()[0].effect(game)

        assert walker.last_surveil_result.ordered_top_to_bottom == [second, top]
        assert p1.zones[Zone.LIBRARY].get_all() == [bottom, top, second]
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0

    def test_minus_one_can_target_zero_players_and_do_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = CardImpl(name="Keep This")
        second = CardImpl(name="Keep That")

        set_board_state(game, 0, hand=[first])
        set_board_state(game, 1, hand=[second])

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = []
        walker.get_loyalty_abilities()[1].effect(game)

        assert p1.zones[Zone.HAND].contains(first)
        assert p2.zones[Zone.HAND].contains(second)
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = CardImpl(name="First Draft")
        second = CardImpl(name="Second Draft")
        third = CardImpl(name="Third Draft")

        set_board_state(game, 0, hand=[first, second])
        set_board_state(game, 1, hand=[third])
        p1._script.appendleft(first)
        p2._script.appendleft(third)

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p1, p2]
        walker.get_loyalty_abilities()[1].effect(game)

        assert not p1.zones[Zone.HAND].contains(first)
        assert p1.zones[Zone.HAND].contains(second)
        assert p1.zones[Zone.GRAVEYARD].contains(first)
        assert not p2.zones[Zone.HAND].contains(third)
        assert p2.zones[Zone.GRAVEYARD].contains(third)

    def test_minus_one_ignores_targeted_players_with_empty_hands(self) -> None:
        game = create_game()
        p1, p2 = game.players
        only_card = CardImpl(name="Only Card")

        set_board_state(game, 0, hand=[])
        set_board_state(game, 1, hand=[only_card])
        p2._script.appendleft(only_card)

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [p1, p2]
        walker.get_loyalty_abilities()[1].effect(game)

        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0
        assert not p2.zones[Zone.HAND].contains(only_card)
        assert p2.zones[Zone.GRAVEYARD].contains(only_card)

    def test_minus_one_can_choose_multiple_players_through_normal_activation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = CardImpl(name="First Draft")
        second = CardImpl(name="Second Draft")
        third = CardImpl(name="Third Draft")
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[walker], hand=[first, second])
        set_board_state(game, 1, hand=[third])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p1._script.extend([[p1, p2], first])
        p2._script.append(third)

        ability = walker.create_loyalty_ability_instance(1)
        activate_ability(game, p1, ability)

        assert walker.loyalty == 2
        assert walker.chosen_targets == [p1, p2]
        assert game.stack.peek().targets == [p1, p2]

        game.stack.pop().on_resolve(game)

        assert not p1.zones[Zone.HAND].contains(first)
        assert p1.zones[Zone.HAND].contains(second)
        assert p1.zones[Zone.GRAVEYARD].contains(first)
        assert not p2.zones[Zone.HAND].contains(third)
        assert p2.zones[Zone.GRAVEYARD].contains(third)

    def test_minus_two_returns_small_creature_from_your_graveyard_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        returned = Creature(
            name="Returned Pupil",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, graveyard=[returned])

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [returned]
        walker.get_loyalty_abilities()[2].effect(game)

        assert not p1.zones[Zone.GRAVEYARD].contains(returned)
        assert p1.zones[Zone.BATTLEFIELD].contains(returned)

    def test_minus_two_leaves_mana_value_four_creature_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        oversized = Creature(
            name="Oversized Thesis",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, graveyard=[oversized])

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [oversized]
        walker.get_loyalty_abilities()[2].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(oversized)
        assert not p1.zones[Zone.BATTLEFIELD].contains(oversized)

    def test_minus_two_cannot_return_creature_from_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        opposing_creature = Creature(
            name="Stolen Subject",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 1, graveyard=[opposing_creature])

        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.chosen_targets = [opposing_creature]
        walker.get_loyalty_abilities()[2].effect(game)

        assert p2.zones[Zone.GRAVEYARD].contains(opposing_creature)
        assert not p1.zones[Zone.BATTLEFIELD].contains(opposing_creature)

    def test_minus_seven_uses_scripted_coin_flips_and_consumes_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        walker.loyalty = 7

        set_board_state(game, 0, battlefield=[walker])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.queue_coin_flips([True, False, True, True, False])
        p1._script.append(p2)

        ability = walker.create_loyalty_ability_instance(3)
        activate_ability(game, p1, ability)

        assert walker.loyalty == 0
        assert walker.chosen_targets == [p2]

        game.stack.pop().on_resolve(game)

        assert walker.last_coin_flip_results == [True, False, True, True, False]
        assert walker.last_coin_flip_heads == 3
        assert game.coin_flip_history == [True, False, True, True, False]
        assert game.skip_next_turns == {1: 3}

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.turn_number == 3
        assert game.skip_next_turns == {1: 2}

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.turn_number == 5
        assert game.skip_next_turns == {1: 1}

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.turn_number == 7
        assert game.skip_next_turns == {}
