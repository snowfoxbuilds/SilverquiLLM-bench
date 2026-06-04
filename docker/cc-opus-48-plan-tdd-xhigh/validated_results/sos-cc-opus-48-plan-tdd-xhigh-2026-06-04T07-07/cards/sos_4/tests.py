"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(game, player_index, n):
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1)
        c.owner = player
        lib.add(c)


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


class TestTogetherAsOneConverge:
    """Cast through the real pipeline so the engine sets colors_spent."""

    def test_three_colors_draws_damages_gains(self) -> None:
        spell = TogetherAsOne(owner=None)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[spell], life=20)
        set_board_state(game, 1, life=20)
        _fill_library(game, 0, 5)
        # {6} paid with W,U,B (2 each) -> 3 distinct colors -> X=3.
        set_board_state(game, 0, mana={ManaType.WHITE: 2, ManaType.BLUE: 2,
                                       ManaType.BLACK: 2})
        lib_before = len(game.players[0].zones[Zone.LIBRARY])
        # Target player0 to draw, player1 takes the damage.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert lib_before - len(game.players[0].zones[Zone.LIBRARY]) == 3
        assert p2.life == 17
        assert p1.life == 23

    def test_zero_colors_all_noop(self) -> None:
        spell = TogetherAsOne(owner=None)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[spell], life=20)
        set_board_state(game, 1, life=20)
        _fill_library(game, 0, 5)
        # {6} paid entirely with colorless -> 0 colors -> X=0.
        set_board_state(game, 0, mana={ManaType.COLORLESS: 6})
        lib_before = len(game.players[0].zones[Zone.LIBRARY])
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert lib_before - len(game.players[0].zones[Zone.LIBRARY]) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_damage_can_target_a_creature(self) -> None:
        spell = TogetherAsOne(owner=None)
        creature = Creature(name="Victim", base_power=2, base_toughness=4)
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, hand=[spell])
        set_board_state(game, 1, battlefield=[creature])
        _fill_library(game, 0, 5)
        # Two colors -> X=2.
        set_board_state(game, 0, mana={ManaType.RED: 3, ManaType.GREEN: 3})
        cast_spell(game, 0, "Together as One", targets=[p1, creature])
        assert creature.damage_marked == 2

