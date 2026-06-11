"""Tests for Together as One (sos_4)."""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _game_with_spell():
    spell = TogetherAsOne()
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]
    set_board_state(game, 0, hand=[spell])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    return game, spell, p1, p2


def test_x_zero_when_colorless():
    """X = 0 when paid with only colorless mana."""
    game, spell, p1, p2 = _game_with_spell()
    p1.mana_pool.add(ManaType.COLORLESS, 6)
    p2_life_before = p2.life
    p1_life_before = p1.life

    cast_spell(game, 0, "Together as One", targets=[p2, p2])

    assert p2.life == p2_life_before   # 0 damage
    assert p1.life == p1_life_before   # 0 life gained
    # p2 drew 0 cards — hand size unchanged


def test_x_equals_colors_spent():
    """X = 3 when paid with 3 different colored mana."""
    game, spell, p1, p2 = _game_with_spell()
    # Pay {6} with 2 red + 2 green + 2 blue → X = 3
    p1.mana_pool.add(ManaType.RED, 2)
    p1.mana_pool.add(ManaType.GREEN, 2)
    p1.mana_pool.add(ManaType.BLUE, 2)
    dummy_creature = Creature(name="Dummy", base_power=1, base_toughness=1)
    set_board_state(game, 1, battlefield=[dummy_creature])
    p1_life_before = p1.life

    cast_spell(game, 0, "Together as One", targets=[p1, dummy_creature])

    # X = 3: p1 drew 3 cards, dummy took 3 damage, p1 gained 3 life
    assert dummy_creature.damage_marked == 3
    assert p1.life == p1_life_before + 3


def test_x_one_single_color():
    """X = 1 when all mana is one color."""
    game, spell, p1, p2 = _game_with_spell()
    p1.mana_pool.add(ManaType.WHITE, 6)
    p2_life_before = p2.life
    p1_life_before = p1.life

    cast_spell(game, 0, "Together as One", targets=[p2, p2])

    assert p2.life == p2_life_before - 1   # 1 damage
    assert p1.life == p1_life_before + 1   # 1 life gained


def test_targets_player_draws():
    """Target player draws X cards."""
    game, spell, p1, p2 = _game_with_spell()
    # Give p2 a library
    filler = Creature(name="Filler", base_power=1, base_toughness=1)
    filler2 = Creature(name="Filler2", base_power=1, base_toughness=1)
    filler3 = Creature(name="Filler3", base_power=1, base_toughness=1)
    p2.zones[Zone.LIBRARY].add(filler)
    p2.zones[Zone.LIBRARY].add(filler2)
    p2.zones[Zone.LIBRARY].add(filler3)
    p2_hand_before = len(game.get_hand(p2).get_all())

    # Pay with 2 colors → X = 2
    p1.mana_pool.add(ManaType.WHITE, 3)
    p1.mana_pool.add(ManaType.BLUE, 3)

    cast_spell(game, 0, "Together as One", targets=[p2, p2])

    assert len(game.get_hand(p2).get_all()) == p2_hand_before + 2
