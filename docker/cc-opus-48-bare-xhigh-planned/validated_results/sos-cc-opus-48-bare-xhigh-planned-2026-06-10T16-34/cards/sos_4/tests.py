"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import Color, ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _fill_library(game, player_index, n):
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        c = Creature(name=f"Filler{i}", base_power=1, base_toughness=1)
        c.owner = player
        c.controller = player
        lib.add(c)


class TestProperties:
    def test_name_and_type(self):
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert isinstance(card, Sorcery)

    def test_mana_cost(self):
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConvergeRealCast:
    def test_three_colors_draws_deals_gains_three(self):
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        hand_before = len(p1.zones[Zone.HAND].get_all())  # includes the spell
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # X = 3 colors (W,U,B). p1 draws 3, p2 takes 3 damage, p1 gains 3 life.
        # Hand: started with [spell]; spell leaves to graveyard, +3 drawn = 3.
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before - 1 + 3
        assert p2.life == 17
        assert p1.life == 23
        assert game.get_graveyard(p1).contains(card)

    def test_zero_colors_does_nothing(self):
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # X = 0 → no draws, no damage, no life gain.
        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert p2.life == 20
        assert p1.life == 20


class TestConvergeResolveLogic:
    def test_damage_to_creature_target(self):
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE]  # X = 2
        card.chosen_targets = [p1, bear]
        card.on_resolve(game)
        assert bear.damage_marked == 2
        assert p1.life == 22
        assert len(p1.zones[Zone.HAND].get_all()) == 2

    def test_x_equals_one(self):
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, 1, 3)  # p2 is the draw target
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.RED]  # X = 1
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)
        assert p2.life == 19  # 1 damage
        assert p1.life == 21  # 1 life gained
        assert len(p2.zones[Zone.HAND].get_all()) == 1  # p2 drew 1
