"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

from unittest.mock import patch

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    advance_to_phase,
    create_game,
    set_board_state,
    _resolve_top_of_stack,
)


class BearCreature(Creature):
    def __init__(self, name="Bear", mv=2, **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=mv))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class SmallInstant(Instant):
    def __init__(self, name="TestInstant", **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=1))
        super().__init__(**kwargs)


def _activate_loyalty(game, player, ral, ability_index):
    """Helper: activate Ral's loyalty ability at given index, resolve the stack."""
    clear_loyalty_tracking()
    abilities = ral.get_loyalty_abilities()
    la = abilities[ability_index]
    inst = LoyaltyAbilityInstance(
        source=ral,
        controller=player,
        loyalty_cost=la.loyalty_cost,
        effect=la.effect,
        description=la.description,
    )
    activate_ability(game, player, inst)


def test_surveil_2_puts_card_in_graveyard():
    """+1 (Surveil 2) allows player to put cards into graveyard."""
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]

    ral = RalZarekGuestLecturer()
    lib_card1 = BearCreature(name="LibBear1")
    lib_card2 = BearCreature(name="LibBear2")
    for c in [lib_card1, lib_card2]:
        c.owner = p1
        c.controller = p1
        game.get_library(p1).add(c)

    set_board_state(game, 0, battlefield=[ral])
    ral.controller = p1
    ral.loyalty = 3

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(True)   # put lib_card1 in graveyard
        p1._script.appendleft(False)  # keep lib_card2 on top

    _activate_loyalty(game, p1, ral, 0)  # +1 Surveil 2
    _resolve_top_of_stack(game)

    gy = game.get_graveyard(p1).get_all()
    # At least one card went to graveyard
    assert len(gy) >= 1
    # Loyalty was increased by 1
    assert ral.loyalty == 4


def test_minus1_discards_target_players():
    """-1 ability makes target players discard."""
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    ral = RalZarekGuestLecturer()
    hand_card = SmallInstant()
    hand_card.owner = p2
    hand_card.controller = p2

    set_board_state(game, 0, battlefield=[ral])
    set_board_state(game, 1, hand=[hand_card])
    ral.controller = p1
    ral.loyalty = 3

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(hand_card)  # choose card for p2 to discard
        p1._script.appendleft(True)       # yes, include p2
        p1._script.appendleft(False)      # no, don't target p1

    _activate_loyalty(game, p1, ral, 1)  # -1
    _resolve_top_of_stack(game)

    assert hand_card in game.get_graveyard(p2).get_all()
    assert ral.loyalty == 2


def test_minus2_returns_creature_from_graveyard():
    """-2 ability returns creature with MV ≤ 3 from graveyard to battlefield."""
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]

    ral = RalZarekGuestLecturer()
    small_creature = BearCreature(name="SmallBear", mv=2)
    small_creature.owner = p1
    small_creature.controller = p1

    set_board_state(game, 0, battlefield=[ral])
    game.get_graveyard(p1).add(small_creature)

    ral.controller = p1
    ral.loyalty = 5

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(small_creature)

    _activate_loyalty(game, p1, ral, 2)  # -2
    _resolve_top_of_stack(game)

    # Creature should be on battlefield, not in graveyard.
    assert small_creature in game.get_battlefield(p1).get_all()
    assert small_creature not in game.get_graveyard(p1).get_all()
    assert ral.loyalty == 3


def test_minus7_coin_flips_cause_opponent_to_skip_turns():
    """-7 ability: all heads → opponent skips 5 turns."""
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    ral.controller = p1
    ral.loyalty = 10

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    # Patch random to always return heads (< 0.5)
    with patch("cards.sos.sos_97.card_impl.random.random", return_value=0.0):
        _activate_loyalty(game, p1, ral, 3)  # -7
        _resolve_top_of_stack(game)

    # 5 heads → p2 should skip 5 turns
    assert p2.skip_turns == 5
    assert ral.loyalty == 3


def test_minus7_all_tails_no_skip():
    """-7 ability: all tails → opponent skips 0 turns."""
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    ral.controller = p1
    ral.loyalty = 10

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    # Patch random to always return tails (>= 0.5)
    with patch("cards.sos.sos_97.card_impl.random.random", return_value=1.0):
        _activate_loyalty(game, p1, ral, 3)
        _resolve_top_of_stack(game)

    assert p2.skip_turns == 0


def test_skip_turns_engine_integration():
    """Engine advance_phase correctly skips player turns when skip_turns > 0."""
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    p2.skip_turns = 2

    # Advance through end of p1's turn and into the next turn.
    # With skip_turns=2, p2 should be skipped and p1 should play again.
    orig_turn = game.turn_number
    for _ in range(100):
        game.advance_phase()
        if game.turn_number > orig_turn:
            # Should be p1's turn (p2 was skipped).
            assert game.active_player is p1, f"Expected p1 to play, got {game.active_player.name}. p2.skip_turns={p2.skip_turns}"
            break
