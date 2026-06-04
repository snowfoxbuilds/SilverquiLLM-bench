"""Tests for Ral Zarek, Guest Lecturer (SOS 97)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer, surveil
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import card_colors, create_game, set_board_state


def _creature(name: str, mv: int = 2) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(f"{{{mv}}}"),
        base_power=2,
        base_toughness=2,
    )


def _vanilla(name: str) -> Creature:
    # A library card stand-in (real card object so name/zone checks work).
    return Creature(name=name, base_power=1, base_toughness=1)


def _ability(ral: RalZarekGuestLecturer, cost: int):
    for a in ral.get_loyalty_abilities():
        if a.loyalty_cost == cost:
            return a
    raise AssertionError(f"no loyalty ability with cost {cost}")


class TestRalProperties:
    def test_is_planeswalker(self) -> None:
        ral = RalZarekGuestLecturer(owner=None)
        assert isinstance(ral, Planeswalker)
        assert CardType.PLANESWALKER in ral.card_types

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        ral = RalZarekGuestLecturer(owner=None)
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3

    def test_legendary_ral(self) -> None:
        ral = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in ral.supertypes
        assert "Ral" in ral.subtypes

    def test_black(self) -> None:
        assert card_colors(RalZarekGuestLecturer(owner=None)) == {"B"}

    def test_loyalty_ability_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert [a.loyalty_cost for a in abilities] == [1, -1, -2, -7]


class TestSurveil:
    def test_plus1_surveils_two(self) -> None:
        # script: put top card in gy, keep the next one.
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        c1, c2, c3 = _vanilla("c1"), _vanilla("c2"), _vanilla("c3")
        lib = p1.zones[Zone.LIBRARY]
        for c in (c1, c2, c3):  # c3 ends up on top
            lib.add(c)
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _ability(ral, 1).effect(game)
        gy = p1.zones[Zone.GRAVEYARD]
        assert gy.contains(c3)
        assert lib.contains(c2) and lib.contains(c1)
        assert not lib.contains(c3)

    def test_surveil_helper_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # No cards in library — must not raise.
        surveil(game, p1, 2)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_surveil_keeps_all_when_declined(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        a, b = _vanilla("a"), _vanilla("b")
        for c in (a, b):
            p1.zones[Zone.LIBRARY].add(c)
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _ability(ral, 1).effect(game)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert p1.zones[Zone.LIBRARY].contains(a)
        assert p1.zones[Zone.LIBRARY].contains(b)


class TestDiscard:
    def test_minus1_target_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _vanilla("HandCard")
        set_board_state(game, 1, hand=[card])
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2
        _ability(ral, -1).effect(game)
        assert not p2.zones[Zone.HAND].contains(card)
        assert p2.zones[Zone.GRAVEYARD].contains(card)

    def test_minus1_multiple_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        my_card = _vanilla("Mine")
        opp_card = _vanilla("Theirs")
        set_board_state(game, 0, hand=[my_card])
        set_board_state(game, 1, hand=[opp_card])
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_targets = [p1, p2]
        _ability(ral, -1).effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(my_card)
        assert p2.zones[Zone.GRAVEYARD].contains(opp_card)

    def test_minus1_empty_hand_no_crash(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2
        _ability(ral, -1).effect(game)  # no hand cards -> no-op
        assert len(p2.zones[Zone.GRAVEYARD]) == 0


class TestReanimate:
    def test_minus2_returns_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        body = _creature("Body", mv=3)
        set_board_state(game, 0, graveyard=[body])
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = body
        _ability(ral, -2).effect(game)
        assert p1.zones[Zone.BATTLEFIELD].contains(body)
        assert not p1.zones[Zone.GRAVEYARD].contains(body)

    def test_minus2_rejects_high_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]
        body = _creature("Big", mv=4)
        set_board_state(game, 0, graveyard=[body])
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = body
        _ability(ral, -2).effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(body)
        assert not p1.zones[Zone.BATTLEFIELD].contains(body)

    def test_minus2_rejects_noncreature(self) -> None:
        from engine.card import Sorcery

        game = create_game()
        p1 = game.players[0]
        spell = Sorcery(name="Spell", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, graveyard=[spell])
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = spell
        _ability(ral, -2).effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert not p1.zones[Zone.BATTLEFIELD].contains(spell)

    def test_minus2_requires_card_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        body = _creature("Loose", mv=2)
        body.owner = p1
        body.controller = p1
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = body  # not in any graveyard
        _ability(ral, -2).effect(game)
        assert not p1.zones[Zone.BATTLEFIELD].contains(body)


class TestUltimateCoinFlips:
    def test_minus7_skips_per_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game._scripted_coin_flips = [True, True, True, False, False]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2
        _ability(ral, -7).effect(game)
        assert game.skipped_turns.get(1) == 3

    def test_minus7_zero_heads_no_skip(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game._scripted_coin_flips = [False, False, False, False, False]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p2
        _ability(ral, -7).effect(game)
        assert 1 not in game.skipped_turns

    def test_minus7_ignores_self_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game._scripted_coin_flips = [True, True, True, True, True]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral._resolve_target = p1  # not an opponent
        _ability(ral, -7).effect(game)
        assert game.skipped_turns == {}


def _advance_one_turn(game: Any) -> None:
    start = game.turn_number
    guard = 0
    while game.turn_number == start and guard < 50:
        game.advance_phase()
        guard += 1


class TestSkipTurnMechanism:
    def test_skip_one_turn(self) -> None:
        game = create_game()
        # Turn 1: P0 active. P1 must skip their next turn.
        assert game.active_player_index == 0
        game.skipped_turns = {1: 1}
        _advance_one_turn(game)
        # P1's turn 2 is skipped -> P0 takes turn 2.
        assert game.active_player_index == 0
        _advance_one_turn(game)
        # P1 resumes on turn 3.
        assert game.active_player_index == 1

    def test_skip_two_turns(self) -> None:
        game = create_game()
        game.skipped_turns = {1: 2}
        _advance_one_turn(game)
        assert game.active_player_index == 0
        _advance_one_turn(game)
        assert game.active_player_index == 0
        _advance_one_turn(game)
        assert game.active_player_index == 1

    def test_no_skip_normal_rotation(self) -> None:
        game = create_game()
        _advance_one_turn(game)
        assert game.active_player_index == 1
        _advance_one_turn(game)
        assert game.active_player_index == 0
