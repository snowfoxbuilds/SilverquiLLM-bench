"""Tests for Ral Zarek, Guest Lecturer (SOS #97)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _creature(name: str, mv: int = 2) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(f"{{{mv}}}"),
        base_power=2,
        base_toughness=2,
    )


def _set_library(game: Any, idx: int, cards_top_first: list[Any]) -> None:
    player = game.players[idx]
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in reversed(cards_top_first):
        c.owner = player
        c.controller = player
        lib.add(c)


def _setup_sorcery_timing(game: Any) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0


def _activate(game: Any, ral: RalZarekGuestLecturer, player: Any, loyalty_cost: int) -> None:
    clear_loyalty_tracking()
    ability_def = next(
        a for a in ral.get_loyalty_abilities() if a.loyalty_cost == loyalty_cost
    )
    inst = LoyaltyAbilityInstance(
        source=ral,
        controller=player,
        loyalty_cost=ability_def.loyalty_cost,
        effect=ability_def.effect,
        description=ability_def.description,
    )
    activate_ability(game, player, inst)
    _resolve_all(game)


def test_basic_characteristics():
    card = RalZarekGuestLecturer()
    assert CardType.PLANESWALKER in card.card_types
    assert Supertype.LEGENDARY in card.supertypes
    assert "Ral" in card.subtypes
    assert card.mana_cost.generic == 1
    assert card.starting_loyalty == 3
    assert card.loyalty == 3

    costs = sorted(a.loyalty_cost for a in card.get_loyalty_abilities())
    assert costs == [-7, -2, -1, 1]


def test_plus1_surveils_two():
    game = create_game()
    p1, _ = game.players

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    _setup_sorcery_timing(game)

    top, second = _creature("Top"), _creature("Second")
    _set_library(game, 0, [top, second])

    # Surveil 2 examines top-first: bin the top card, keep the second.
    p1._script = deque([True, False])
    _activate(game, ral, p1, +1)

    assert ral.loyalty == 4
    assert game.get_graveyard(p1).contains(top)
    assert not game.get_graveyard(p1).contains(second)
    # Kept card remains on top of the library.
    assert game.get_library(p1).top(1)[0] is second


def test_minus1_target_players_discard():
    game = create_game()
    p1, p2 = game.players

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    _setup_sorcery_timing(game)

    mine, theirs = _creature("Mine"), _creature("Theirs")
    set_board_state(game, 0, battlefield=[ral], hand=[mine])
    set_board_state(game, 1, hand=[theirs])

    # Both players are targeted; each chooses the card to discard.
    ral._resolve_target = [p1, p2]
    p1._script = deque([mine])
    p2._script = deque([theirs])

    _activate(game, ral, p1, -1)

    assert ral.loyalty == 2
    assert game.get_graveyard(p1).contains(mine)
    assert game.get_graveyard(p2).contains(theirs)
    assert len(game.get_hand(p1).get_all()) == 0
    assert len(game.get_hand(p2).get_all()) == 0


def test_minus2_reanimates_small_creature():
    game = create_game()
    p1, _ = game.players

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    _setup_sorcery_timing(game)

    victim = _creature("Reanimated", mv=3)
    set_board_state(game, 0, battlefield=[ral], graveyard=[victim])

    ral._resolve_target = victim
    _activate(game, ral, p1, -2)

    assert ral.loyalty == 1
    assert game.get_battlefield(p1).contains(victim)
    assert not game.get_graveyard(p1).contains(victim)
    assert victim.controller is p1


def test_minus2_ignores_creature_above_mv_three():
    game = create_game()
    p1, _ = game.players

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    _setup_sorcery_timing(game)

    big = _creature("TooBig", mv=4)
    set_board_state(game, 0, battlefield=[ral], graveyard=[big])

    ral._resolve_target = big
    _activate(game, ral, p1, -2)

    # Loyalty cost is still paid, but the creature stays in the graveyard.
    assert ral.loyalty == 1
    assert game.get_graveyard(p1).contains(big)
    assert not game.get_battlefield(p1).contains(big)


def test_minus7_sets_skip_turns_by_heads():
    game = create_game()
    p1, p2 = game.players

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    _setup_sorcery_timing(game)
    # Pretend Ral has ticked up to 7 loyalty.
    ral.loyalty = 7

    # Five coin flips: three heads.
    p1._script = deque([True, True, False, True, False])
    ral._resolve_target = p2

    _activate(game, ral, p1, -7)

    assert ral.loyalty == 0
    assert game.skip_turns[game.players.index(p2)] == 3


def test_skip_turns_rotation_is_honored():
    game = create_game()

    # Player 1 (seat 0) just finished a turn; seat 1 owes one skipped turn.
    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.active_player_index = 0
    game._normal_next_index = 1
    game.skip_turns = {1: 1}

    game.advance_phase()
    # Seat 1's turn is skipped, so seat 0 takes the next turn instead.
    assert game.active_player_index == 0
    assert game.skip_turns[1] == 0

    # The following turn proceeds normally to seat 1.
    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.advance_phase()
    assert game.active_player_index == 1
