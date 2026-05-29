"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_legendary_planeswalker_with_printed_mana_cost_and_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """The printed loyalty abilities should be declared on the card."""

    def test_declares_four_loyalty_abilities_with_printed_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        descriptions = [ability.description.lower() for ability in abilities]
        assert "surveil 2" in descriptions[0]
        assert "discard a card" in descriptions[1]
        assert "mana value 3 or less" in descriptions[2]
        assert "flip five coins" in descriptions[3]


class TestRalZarekGuestLecturerSurveil:
    """The +1 ability should surveil 2."""

    @staticmethod
    def _library_card(name: str) -> Instant:
        return Instant(name=name, mana_cost=ManaCost.parse("{U}"))

    def test_plus_one_moves_only_chosen_cards_from_the_top_two_into_graveyard(self) -> None:
        top = self._library_card("Top Card")
        second = self._library_card("Second Card")
        filler = self._library_card("Filler Card")
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        library = p1.zones[Zone.LIBRARY]
        graveyard = p1.zones[Zone.GRAVEYARD]

        library.add(filler)
        library.add(second)
        library.add(top)

        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.get_loyalty_abilities()[0].effect(game)

        assert graveyard.contains(top) is True
        assert graveyard.contains(second) is False
        assert library.contains(second) is True
        assert library.contains(filler) is True

    def test_plus_one_only_uses_available_cards_when_library_has_fewer_than_two(self) -> None:
        only_card = self._library_card("Only Card")
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        p1.zones[Zone.LIBRARY].add(only_card)

        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.get_loyalty_abilities()[0].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(only_card) is True
        assert p1.zones[Zone.LIBRARY].contains(only_card) is False


class TestRalZarekGuestLecturerDiscard:
    """The −1 ability should make each targeted player discard a card."""

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{B}"))
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, hand=[keep])

        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = []

        card.get_loyalty_abilities()[1].effect(game)

        assert p1.zones[Zone.HAND].contains(keep) is True
        assert p1.zones[Zone.GRAVEYARD].contains(keep) is False

    def test_minus_one_makes_each_targeted_player_discard_one_card(self) -> None:
        p1_card = Instant(name="Lecture Notes", mana_cost=ManaCost.parse("{B}"))
        p2_card = Instant(name="Term Paper", mana_cost=ManaCost.parse("{U}"))
        game = create_game(scripts=([p1_card], [p2_card]))
        p1, p2 = game.players
        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])

        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p1, p2]

        card.get_loyalty_abilities()[1].effect(game)

        assert p1.zones[Zone.HAND].contains(p1_card) is False
        assert p1.zones[Zone.GRAVEYARD].contains(p1_card) is True
        assert p2.zones[Zone.HAND].contains(p2_card) is False
        assert p2.zones[Zone.GRAVEYARD].contains(p2_card) is True


class TestRalZarekGuestLecturerReanimation:
    """The −2 ability should reanimate only an eligible creature card from your graveyard."""

    @staticmethod
    def _creature(name: str, cost: str) -> Creature:
        return Creature(
            name=name,
            mana_cost=ManaCost.parse(cost),
            base_power=2,
            base_toughness=2,
        )

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = self._creature("Assistant", "{2}{B}")
        set_board_state(game, 0, graveyard=[target])

        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.get_loyalty_abilities()[2].effect(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(target) is True
        assert p1.zones[Zone.GRAVEYARD].contains(target) is False

    def test_minus_two_does_not_return_a_creature_card_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = self._creature("Borrowed Assistant", "{2}{B}")
        set_board_state(game, 1, graveyard=[target])

        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.get_loyalty_abilities()[2].effect(game)

        assert p2.zones[Zone.GRAVEYARD].contains(target) is True
        assert p1.zones[Zone.BATTLEFIELD].contains(target) is False

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = self._creature("Senior Assistant", "{3}{B}")
        set_board_state(game, 0, graveyard=[target])

        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.get_loyalty_abilities()[2].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(target) is True
        assert p1.zones[Zone.BATTLEFIELD].contains(target) is False


class TestRalZarekGuestLecturerUltimate:
    """The −7 ability should flip five coins and skip the targeted opponent's turns."""

    def test_minus_seven_flips_five_coins_and_schedules_skips_equal_to_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flips([True, False, True, True, False])

        card.get_loyalty_abilities()[3].effect(game)

        assert game.last_coin_flips == [True, False, True, True, False]
        assert [record.result for record in game.coin_flip_history] == [
            True,
            False,
            True,
            True,
            False,
        ]
        assert all(record.player is p1 for record in game.coin_flip_history)
        assert all(record.source is card for record in game.coin_flip_history)
        assert game.get_pending_skipped_turns(p2) == 3
        assert game.get_pending_skipped_turns(p1) == 0

    def test_minus_seven_with_zero_heads_schedules_no_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flips([False, False, False, False, False])

        card.get_loyalty_abilities()[3].effect(game)

        assert game.last_coin_flips == [False, False, False, False, False]
        assert len(game.coin_flip_history) == 5
        assert game.get_pending_skipped_turns(p2) == 0
        assert game.skipped_turn_history == []

    def test_minus_seven_makes_targeted_opponent_skip_next_x_turns_during_turn_advancement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        game.queue_coin_flips([True, True, False, False, False])

        card.get_loyalty_abilities()[3].effect(game)

        assert game.get_pending_skipped_turns(p2) == 2

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 2
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 3
        assert game.active_player is p1
        assert game.get_pending_skipped_turns(p2) == 0
        assert [
            (record.player_index, record.turn_number, record.from_extra_turn)
            for record in game.skipped_turn_history
        ] == [(1, 2, False), (1, 3, False)]

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 4
        assert game.active_player is p2

    def test_minus_seven_requires_target_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.queue_coin_flips([True, True, True, True, True])

        card.get_loyalty_abilities()[3].effect(game)

        assert game.scripted_coin_flips == [True, True, True, True, True]
        assert game.coin_flip_history == []
        assert game.last_coin_flips == []
        assert game.get_pending_skipped_turns(p1) == 0
        assert game.get_pending_skipped_turns(p2) == 0
