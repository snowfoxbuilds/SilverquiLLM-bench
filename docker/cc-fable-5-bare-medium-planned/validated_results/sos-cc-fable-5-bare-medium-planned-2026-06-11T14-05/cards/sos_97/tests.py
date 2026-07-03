"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.casting import resolve_top
from engine.types import ManaCost, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _ral_on_battlefield(game, player_index=0, loyalty=None):
    ral = RalZarekGuestLecturer()
    set_board_state(game, player_index, battlefield=[ral])
    if loyalty is not None:
        ral.loyalty = loyalty
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_index
    game.priority_player_index = player_index
    clear_loyalty_tracking()
    return ral


def _activate(game, ral, index, targets=None):
    if targets is not None:
        ral.chosen_targets = targets
    ability = ral.get_loyalty_abilities()[index]
    instance = LoyaltyAbilityInstance(
        source=ral, controller=ral.controller,
        loyalty_cost=ability.loyalty_cost, effect=ability.effect,
        description=ability.description,
    )
    activate_ability(game, ral.controller, instance)
    while not game.stack.is_empty():
        resolve_top(game)


class TestRalZarek:
    def test_starting_loyalty(self):
        assert RalZarekGuestLecturer().loyalty == 3

    def test_plus1_surveil_2(self):
        game = create_game()
        p0 = game.players[0]
        ral = _ral_on_battlefield(game)
        bottom = Creature(name="Bottom Card", base_power=1, base_toughness=1)
        top = Creature(name="Top Card", base_power=1, base_toughness=1)
        for c in (bottom, top):
            c.owner = c.controller = p0
            p0.zones[Zone.LIBRARY].add(c)
        p0._script.extend([top, None])  # bin the top card, keep the other
        _activate(game, ral, 0)
        assert ral.loyalty == 4
        assert p0.zones[Zone.GRAVEYARD].contains(top)
        assert p0.zones[Zone.LIBRARY].contains(bottom)

    def test_minus1_each_target_player_discards(self):
        game = create_game()
        p0, p1 = game.players
        ral = _ral_on_battlefield(game)
        c0 = Creature(name="P0 Card", base_power=1, base_toughness=1)
        c1 = Creature(name="P1 Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[c0])
        set_board_state(game, 1, hand=[c1])
        p0._script.append(c0)
        p1._script.append(c1)
        _activate(game, ral, 1, targets=[p0, p1])
        assert ral.loyalty == 2
        assert p0.zones[Zone.GRAVEYARD].contains(c0)
        assert p1.zones[Zone.GRAVEYARD].contains(c1)

    def test_minus1_zero_targets(self):
        game = create_game()
        ral = _ral_on_battlefield(game)
        _activate(game, ral, 1, targets=[])
        assert ral.loyalty == 2

    def test_minus2_reanimates_cheap_creature(self):
        game = create_game()
        p0 = game.players[0]
        ral = _ral_on_battlefield(game)
        bear = Creature(name="Cheap Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        _activate(game, ral, 2, targets=[bear])
        assert ral.loyalty == 1
        assert game.get_battlefield(p0).contains(bear)

    def test_minus2_rejects_mana_value_above_3(self):
        game = create_game()
        p0 = game.players[0]
        ral = _ral_on_battlefield(game)
        ogre = Creature(name="Big Ogre", mana_cost=ManaCost.parse("{3}{R}"),
                        base_power=4, base_toughness=4)
        set_board_state(game, 0, graveyard=[ogre])
        _activate(game, ral, 2, targets=[ogre])
        assert p0.zones[Zone.GRAVEYARD].contains(ogre)
        assert not game.get_battlefield(p0).contains(ogre)

    def test_minus7_coin_flips_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        ral = _ral_on_battlefield(game, loyalty=7)
        game.rng = random.Random(7)
        reference = random.Random(7)
        expected_heads = sum(reference.randint(0, 1) for _ in range(5))
        _activate(game, ral, 3, targets=[p1])
        assert ral.loyalty == 0
        assert p1.skip_turns == expected_heads
        if expected_heads > 0:
            # The opponent's next turn is skipped: after this turn wraps,
            # the active player is p0 again.
            advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
            assert game.active_player is p0
            assert p1.skip_turns == expected_heads - 1

    def test_minus7_requires_loyalty(self):
        game = create_game()
        ral = _ral_on_battlefield(game)  # loyalty 3
        with pytest.raises(AbilityError):
            _activate(game, ral, 3, targets=[game.players[1]])
