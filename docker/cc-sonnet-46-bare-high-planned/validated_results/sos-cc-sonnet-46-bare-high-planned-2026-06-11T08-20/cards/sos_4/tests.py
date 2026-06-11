"""Tests for Together as One (sos_4)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.types import ManaType, Zone
from engine.card import Creature


class TestTogetherAsOne:
    def test_x_zero_colorless_cast(self):
        """X=0 when cast with only colorless mana: no draws, no damage, no life."""
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        # Target p2 for draw, target p1 for damage
        from engine.player import DeterministicPlayer
        p1._script.appendleft(p1)   # any target (damage)
        p1._script.appendleft(p2)   # target player (draw)
        from engine.casting import cast_spell
        from engine.types import Phase
        from test_utils import _resolve_top_of_stack
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, spell)
        _resolve_top_of_stack(game)
        # X = 0 -> p2 draws 0 extra (library was empty), p1 takes 0 damage
        assert p1.life == 20  # no life gain
        assert p2.life == 20  # no damage

    def test_x_two_colors(self):
        """X=2 when cast with 2 colors: draws 2, deals 2, gains 2 life."""
        game = create_game()
        p1, p2 = game.players
        # Put some cards in p2's library
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler2", base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(filler)
        p2.zones[Zone.LIBRARY].add(filler2)
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        # Script: target p2 for draw, target p2 for damage
        p1._script.appendleft(p2)  # any target (damage)
        p1._script.appendleft(p2)  # target player (draw)
        from engine.casting import cast_spell
        from engine.types import Phase
        from test_utils import _resolve_top_of_stack
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, spell)
        _resolve_top_of_stack(game)
        # X=2: p2 draws 2, p2 takes 2 damage, p1 gains 2 life
        hand_count = len(p2.zones[Zone.HAND].get_all())
        assert hand_count == 2
        assert p2.life == 18
        assert p1.life == 22

    def test_x_one_color(self):
        """X=1 when cast with 1 color."""
        game = create_game()
        p1, p2 = game.players
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        p2.zones[Zone.LIBRARY].add(filler)
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 6})
        p1._script.appendleft(p2)  # any target
        p1._script.appendleft(p2)  # target player
        from engine.casting import cast_spell
        from engine.types import Phase
        from test_utils import _resolve_top_of_stack
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, spell)
        _resolve_top_of_stack(game)
        assert p2.life == 19   # -1 damage
        assert p1.life == 21   # +1 life

    def test_damage_to_creature(self):
        """X damage can go to a creature."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        p1._script.appendleft(bear)  # any target = creature
        p1._script.appendleft(p1)   # target player = self for draw
        from engine.casting import cast_spell
        from engine.types import Phase
        from test_utils import _resolve_top_of_stack
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, spell)
        _resolve_top_of_stack(game)
        assert bear.damage_marked == 2  # X=2 damage to creature
        assert p1.life == 22  # +2 life
