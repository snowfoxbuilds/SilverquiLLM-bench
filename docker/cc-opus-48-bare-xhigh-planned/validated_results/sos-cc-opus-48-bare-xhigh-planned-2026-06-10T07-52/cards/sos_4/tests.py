"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(game, player_index, n):
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(CardImpl(name=f"Dummy{i}", owner=player, controller=player))


class TestProperties:
    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_two_colors_draw_damage_life(self) -> None:
        """Two colors spent → X=2: target player draws 2, 2 damage to a
        player, caster gains 2 life."""
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 1, 5)
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 3, ManaType.BLUE: 3},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, p1])

        assert len(p1.zones[Zone.HAND].get_all()) == 2  # drew X=2
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 3
        assert p1.life == 18  # took 2 damage
        assert p0.life == 22  # gained 2 life

    def test_three_colors_damage_to_creature(self) -> None:
        """Three colors → X=3 damage marked on a target creature."""
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 5)
        bear = Creature(name="Big Bear", base_power=4, base_toughness=5)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 2, ManaType.BLACK: 2, ManaType.GREEN: 2},
        )
        cast_spell(game, 0, "Together as One", targets=[p0, bear])

        assert bear.damage_marked == 3
        assert len(p0.zones[Zone.HAND].get_all()) == 3  # p0 drew X=3
        assert p0.life == 23  # gained 3

    def test_zero_colors_colorless(self) -> None:
        """All colorless → X=0: no draw, no damage, no life change."""
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 1, 5)
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, p1])

        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert p1.life == 20
        assert p0.life == 20
