"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _loyalty_ability(card: RalZarekGuestLecturer, cost: int):
    """Return the loyalty ability with the requested loyalty cost."""
    return next(ability for ability in card.get_loyalty_abilities() if ability.loyalty_cost == cost)


def _set_targets(card: RalZarekGuestLecturer, targets: list[object]) -> None:
    """Populate the common target-resolution attributes used in card tests."""
    card.chosen_targets = list(targets)
    card._resolve_targets = list(targets)
    card._resolve_target = targets[0] if targets else None


def _advance_to_next_turn(game) -> None:
    """Advance through the rest of the current turn until the next turn starts."""
    current_turn = game.turn_number
    for _ in range(20):
        game.advance_phase()
        if game.turn_number == current_turn + 1:
            return
    raise AssertionError("game did not advance to the next turn within one full turn cycle")


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_a_legendary_ral_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_has_expected_mana_cost_starting_loyalty_and_rules_text(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert card.rules_text == (
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads."
        )

    def test_exposes_four_loyalty_abilities_with_the_printed_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert [ability.loyalty_cost for ability in card.get_loyalty_abilities()] == [1, -1, -2, -7]


class TestRalZarekGuestLecturerPlusOne:
    """The +1 ability should surveil 2."""

    def test_plus_one_surveils_two_cards_and_moves_only_the_chosen_one_to_graveyard(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        keep = Sorcery(name="Keep Me")
        bin_me = Sorcery(name="Bin Me")

        keep.owner = p1
        keep.controller = p1
        bin_me.owner = p1
        bin_me.controller = p1
        p1.zones[Zone.LIBRARY].add(keep)
        p1.zones[Zone.LIBRARY].add(bin_me)

        _loyalty_ability(card, 1).effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(bin_me)
        assert not p1.zones[Zone.GRAVEYARD].contains(keep)
        assert p1.zones[Zone.LIBRARY].contains(keep)
        assert not p1.zones[Zone.LIBRARY].contains(bin_me)

    def test_plus_one_is_a_noop_with_an_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        _loyalty_ability(card, 1).effect(game)

        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0


class TestRalZarekGuestLecturerMinusOne:
    """The −1 ability should make each targeted player discard a card."""

    def test_each_targeted_player_discards_one_card(self) -> None:
        p1_discard = Sorcery(name="P1 Discard")
        p1_keep = Sorcery(name="P1 Keep")
        p2_discard = Sorcery(name="P2 Discard")
        p2_keep = Sorcery(name="P2 Keep")
        game = create_game(scripts=([p1_discard], [p2_discard]))
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[p1_discard, p1_keep])
        set_board_state(game, 1, hand=[p2_discard, p2_keep])
        _set_targets(card, [p1, p2])

        _loyalty_ability(card, -1).effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(p1_discard)
        assert not p1.zones[Zone.HAND].contains(p1_discard)
        assert p1.zones[Zone.HAND].contains(p1_keep)
        assert p2.zones[Zone.GRAVEYARD].contains(p2_discard)
        assert not p2.zones[Zone.HAND].contains(p2_discard)
        assert p2.zones[Zone.HAND].contains(p2_keep)

    def test_minus_one_with_no_targets_discards_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        p1_card = Sorcery(name="P1 Card")
        p2_card = Sorcery(name="P2 Card")
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        _set_targets(card, [])

        _loyalty_ability(card, -1).effect(game)

        assert p1.zones[Zone.HAND].contains(p1_card)
        assert p2.zones[Zone.HAND].contains(p2_card)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert len(p2.zones[Zone.GRAVEYARD]) == 0


class TestRalZarekGuestLecturerMinusTwo:
    """The −2 ability should reanimate a small creature from your graveyard only."""

    def test_returns_target_creature_card_with_mana_value_three_or_less_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = Creature(
            name="Returned Bear",
            mana_cost=ManaCost.parse("{2}{B}"),
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )

        set_board_state(game, 0, graveyard=[target])
        _set_targets(card, [target])

        _loyalty_ability(card, -2).effect(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(target)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)

    def test_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = Creature(
            name="Too Expensive",
            mana_cost=ManaCost.parse("{3}{B}"),
            owner=p1,
            controller=p1,
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, graveyard=[target])
        _set_targets(card, [target])

        _loyalty_ability(card, -2).effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(target)
        assert not p1.zones[Zone.BATTLEFIELD].contains(target)

    def test_does_not_return_a_creature_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = Creature(
            name="Opposing Bear",
            mana_cost=ManaCost.parse("{2}{B}"),
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=2,
        )

        set_board_state(game, 1, graveyard=[target])
        _set_targets(card, [target])

        _loyalty_ability(card, -2).effect(game)

        assert p2.zones[Zone.GRAVEYARD].contains(target)
        assert not p1.zones[Zone.BATTLEFIELD].contains(target)
        assert not p2.zones[Zone.BATTLEFIELD].contains(target)


class TestRalZarekGuestLecturerMinusSeven:
    """The −7 ability should deterministically flip five coins and skip turns."""

    def test_counts_scripted_heads_and_schedules_that_many_skipped_turns_for_target_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.set_coin_flip_results([True, False, True, False, True])
        _set_targets(card, [p2])

        _loyalty_ability(card, -7).effect(game)

        assert game.pending_skipped_turns(p2) == 3
        assert game.pending_skipped_turns(p1) == 0

    def test_skipped_turns_are_consumed_across_the_target_opponents_next_x_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.set_coin_flip_results([True, True, False, True, False])
        _set_targets(card, [p2])

        _loyalty_ability(card, -7).effect(game)

        _advance_to_next_turn(game)
        assert game.active_player is p1
        assert game.pending_skipped_turns(p2) == 2

        _advance_to_next_turn(game)
        assert game.active_player is p1
        assert game.pending_skipped_turns(p2) == 1

        _advance_to_next_turn(game)
        assert game.active_player is p1
        assert game.pending_skipped_turns(p2) == 0

        _advance_to_next_turn(game)
        assert game.active_player is p2

    def test_does_not_schedule_skipped_turns_if_the_target_is_not_an_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.set_coin_flip_results([True, True, True, True, True])
        _set_targets(card, [p1])

        _loyalty_ability(card, -7).effect(game)

        assert game.pending_skipped_turns(p1) == 0
        assert game.pending_skipped_turns(p2) == 0
