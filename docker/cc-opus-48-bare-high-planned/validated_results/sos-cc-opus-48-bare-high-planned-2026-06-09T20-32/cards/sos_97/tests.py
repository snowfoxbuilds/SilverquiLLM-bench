"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Planeswalker
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate(game, player, pw, index, *, target=None, targets=None):
    clear_loyalty_tracking()
    ab = pw.get_loyalty_abilities()[index]
    if target is not None:
        pw._resolve_target = target
    if targets is not None:
        pw._resolve_targets = targets
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    inst = LoyaltyAbilityInstance(source=pw, controller=player,
                                  loyalty_cost=ab.loyalty_cost, effect=ab.effect)
    activate_ability(game, player, inst)
    _resolve_stack(game)


class TestProperties:
    def test_planeswalker(self):
        c = RalZarekGuestLecturer(owner=None)
        assert isinstance(c, Planeswalker)
        assert c.starting_loyalty == 3 and c.loyalty == 3
        assert Supertype.LEGENDARY in c.supertypes
        assert "Ral" in c.subtypes
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestPlusOneSurveil:
    def test_surveil_bins_and_keeps(self):
        game = create_game(scripts=([True, False], []))
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        a = Creature(name="A", base_power=1, base_toughness=1, owner=p0)
        b = Creature(name="B", base_power=1, base_toughness=1, owner=p0)
        c = Creature(name="C", base_power=1, base_toughness=1, owner=p0)
        for card in (a, b, c):  # top = c
            p0.zones[Zone.LIBRARY].add(card)
        _activate(game, p0, ral, 0)
        assert ral.loyalty == 4
        assert game.get_graveyard(p0).contains(c)   # binned
        assert p0.zones[Zone.LIBRARY].contains(b)    # kept
        assert p0.zones[Zone.LIBRARY].contains(a)    # untouched


class TestMinusOneDiscard:
    def test_target_players_discard(self):
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        junk = Creature(name="Junk", base_power=1, base_toughness=1, owner=p1)
        set_board_state(game, 1, hand=[junk])
        p1._script.append(junk)
        _activate(game, p0, ral, 1, targets=[p1])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(junk)


class TestMinusTwoReanimate:
    def test_returns_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{2}"), owner=p0)
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear])
        _activate(game, p0, ral, 2, target=bear)
        assert ral.loyalty == 1
        assert game.get_battlefield(p0).contains(bear)
        assert not game.get_graveyard(p0).contains(bear)

    def test_too_expensive_not_returned(self):
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        big = Creature(name="Big", base_power=5, base_toughness=5,
                       mana_cost=ManaCost.parse("{4}{R}"), owner=p0)
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        _activate(game, p0, ral, 2, target=big)
        # MV 5 > 3 → stays in graveyard.
        assert game.get_graveyard(p0).contains(big)


class TestUltimate:
    def test_skip_turns_equals_heads(self):
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        seed = 12345
        # Recompute the heads count the same way the card does.
        rng_check = random.Random(seed)
        expected_heads = sum(1 for _ in range(5) if rng_check.randint(0, 1) == 1)
        game.rng = random.Random(seed)
        _activate(game, p0, ral, 3, target=p1)
        assert ral.loyalty == 0
        assert game.skip_turns[1] == expected_heads

    def test_skipped_player_loses_turn(self):
        from engine.types import Step

        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        seed = 7
        rng_check = random.Random(seed)
        heads = sum(1 for _ in range(5) if rng_check.randint(0, 1) == 1)
        game.rng = random.Random(seed)
        _activate(game, p0, ral, 3, target=p1)
        assert game.skip_turns[1] == heads
        if heads >= 1:
            # Finish p0's turn and wrap: p1's turn is skipped → p0 again.
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()
            assert game.active_player_index == 0
            assert game.skip_turns[1] == heads - 1
