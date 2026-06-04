"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _ral() -> RalZarekGuestLecturer:
    return RalZarekGuestLecturer(owner=None)


def _sorcery_speed(game) -> None:
    """Put the game into sorcery-speed timing for player 0."""
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _loyalty_instance(ral, ctrl, index: int) -> LoyaltyAbilityInstance:
    ab = ral.get_loyalty_abilities()[index]
    return LoyaltyAbilityInstance(
        source=ral, controller=ctrl,
        loyalty_cost=ab.loyalty_cost, effect=ab.effect,
        description=ab.description,
    )


def _advance_one_turn(game) -> None:
    start = game.turn_number
    for _ in range(60):
        game.advance_phase()
        if game.turn_number != start:
            return
    raise AssertionError("turn did not advance within a full cycle")


def _creature(name: str, mv: int = 2) -> Creature:
    return Creature(
        name=name, base_power=2, base_toughness=2,
        mana_cost=ManaCost.parse("{" + str(mv) + "}"),
    )


class TestRalProperties:
    def test_name(self) -> None:
        assert _ral().name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert _ral().mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_legendary_planeswalker_ral(self) -> None:
        ral = _ral()
        assert CardType.PLANESWALKER in ral.card_types
        assert Supertype.LEGENDARY in ral.supertypes
        assert "Ral" in ral.subtypes

    def test_starting_loyalty(self) -> None:
        assert _ral().loyalty == 3


class TestRalPlus1Surveil:
    def test_surveil_2_puts_both_in_graveyard(self) -> None:
        ral = _ral()
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[ral])
        a, b, c = _creature("A"), _creature("B"), _creature("C")
        # Library bottom->top is add order, so C is the topmost card.
        for card in (a, b, c):
            p1.zones[Zone.LIBRARY].add(card)
        # Surveil looks at the top two (C, then B); script "yes" for both.
        p1._script.append(True)
        p1._script.append(True)
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 0))
        _resolve_top_of_stack(game)
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert c in gy and b in gy
        assert p1.zones[Zone.LIBRARY].get_all() == [a]
        assert ral.loyalty == 4  # +1

    def test_surveil_2_keeps_both_on_top(self) -> None:
        ral = _ral()
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[ral])
        a, b, c = _creature("A"), _creature("B"), _creature("C")
        for card in (a, b, c):
            p1.zones[Zone.LIBRARY].add(card)
        p1._script.append(False)
        p1._script.append(False)
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 0))
        _resolve_top_of_stack(game)
        assert p1.zones[Zone.GRAVEYARD].get_all() == []
        assert p1.zones[Zone.LIBRARY].get_all() == [a, b, c]
        assert ral.loyalty == 4


class TestRalMinus1Discard:
    def test_each_target_player_discards(self) -> None:
        ral = _ral()
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[ral])
        h1 = _creature("Mine")
        h2 = _creature("Theirs")
        set_board_state(game, 0, hand=[h1])
        set_board_state(game, 1, hand=[h2])
        p1._script.append(h1)
        p2._script.append(h2)
        ral._resolve_targets = [p1, p2]
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 1))
        _resolve_top_of_stack(game)
        assert h1 in p1.zones[Zone.GRAVEYARD].get_all()
        assert h2 in p2.zones[Zone.GRAVEYARD].get_all()
        assert p1.zones[Zone.HAND].get_all() == []
        assert p2.zones[Zone.HAND].get_all() == []
        assert ral.loyalty == 2  # −1

    def test_player_with_empty_hand_is_skipped(self) -> None:
        ral = _ral()
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[ral])
        h1 = _creature("Mine")
        set_board_state(game, 0, hand=[h1])
        set_board_state(game, 1, hand=[])
        p1._script.append(h1)
        ral._resolve_targets = [p1, p2]
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 1))
        _resolve_top_of_stack(game)  # must not raise on empty-handed p2
        assert h1 in p1.zones[Zone.GRAVEYARD].get_all()


class TestRalMinus2Reanimate:
    def test_returns_low_mv_creature_to_battlefield(self) -> None:
        ral = _ral()
        game = create_game()
        p1 = game.players[0]
        zombie = _creature("Zombie", mv=3)
        set_board_state(game, 0, battlefield=[ral], graveyard=[zombie])
        ral._resolve_target = zombie
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 2))
        _resolve_top_of_stack(game)
        assert zombie in game.get_battlefield(p1).get_all()
        assert zombie not in p1.zones[Zone.GRAVEYARD].get_all()
        assert zombie.summoning_sick is True
        assert ral.loyalty == 1  # −2

    def test_does_not_return_high_mv_creature(self) -> None:
        ral = _ral()
        game = create_game()
        p1 = game.players[0]
        big = _creature("Behemoth", mv=5)
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        ral._resolve_target = big
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 2))
        _resolve_top_of_stack(game)
        assert big in p1.zones[Zone.GRAVEYARD].get_all()
        assert big not in game.get_battlefield(p1).get_all()

    def test_does_not_return_noncreature_card(self) -> None:
        ral = _ral()
        game = create_game()
        p1 = game.players[0]
        spell = Sorcery(name="Bolt", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[ral], graveyard=[spell])
        ral._resolve_target = spell
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 2))
        _resolve_top_of_stack(game)
        assert spell in p1.zones[Zone.GRAVEYARD].get_all()
        assert spell not in game.get_battlefield(p1).get_all()


class TestRalMinus7SkipTurns:
    def test_opponent_skips_turns_equal_to_heads(self) -> None:
        ral = _ral()
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        ral._resolve_target = p2
        ral._flip_five_coins = lambda: 3
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 3))
        _resolve_top_of_stack(game)
        assert game.skipped_turns.get(1, 0) == 3

    def test_zero_heads_skips_no_turns(self) -> None:
        ral = _ral()
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        ral._resolve_target = p2
        ral._flip_five_coins = lambda: 0
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 3))
        _resolve_top_of_stack(game)
        assert game.skipped_turns.get(1, 0) == 0

    def test_skip_actually_skips_opponent_next_turn(self) -> None:
        ral = _ral()
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        ral._resolve_target = p2
        ral._flip_five_coins = lambda: 1
        _sorcery_speed(game)
        activate_ability(game, p1, _loyalty_instance(ral, p1, 3))
        _resolve_top_of_stack(game)
        # Opponent (seat 1) should be skipped on the next rotation.
        _advance_one_turn(game)
        assert game.active_player_index == 0
        assert game.skipped_turns.get(1, 0) == 0
        # Following rotation, the opponent finally takes their turn.
        _advance_one_turn(game)
        assert game.active_player_index == 1
