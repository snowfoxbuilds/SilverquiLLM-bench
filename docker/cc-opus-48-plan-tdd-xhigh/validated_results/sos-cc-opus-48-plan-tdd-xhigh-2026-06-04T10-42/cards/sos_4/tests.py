"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(game, player_index: int, n: int) -> list:
    library = game.players[player_index].zones[Zone.LIBRARY]
    cards = []
    for i in range(n):
        c = CardImpl(name=f"Filler{i}")
        c.owner = game.players[player_index]
        c.controller = game.players[player_index]
        library.add(c)
        cards.append(c)
    return cards


class TestTogetherAsOneProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneResolution:
    def test_converge_five_colors(self) -> None:
        game = create_game()
        p0, p1 = game.players
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell], life=20)
        set_board_state(game, 1, life=20)
        _fill_library(game, 0, 5)
        # Pay {6} with WUBRG + 1 colorless → 5 distinct colors spent.
        set_board_state(game, 0, mana={
            ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
            ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1,
        })

        cast_spell(game, 0, "Together as One", targets=[p0, p1])

        # Target player (caster) drew 5.
        assert len(game.get_hand(p0)) == 5
        # Any target (opponent) took 5 damage.
        assert p1.life == 15
        # Controller gained 5 life.
        assert p0.life == 25

    def test_converge_zero_colors_is_noop(self) -> None:
        game = create_game()
        p0, p1 = game.players
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell], life=20)
        set_board_state(game, 1, life=20)
        _fill_library(game, 0, 5)
        # Pay {6} entirely with colorless → 0 colors spent.
        set_board_state(game, 0, mana={ManaType.COLORLESS: 6})

        cast_spell(game, 0, "Together as One", targets=[p0, p1])

        assert len(game.get_hand(p0)) == 0
        assert p1.life == 20
        assert p0.life == 20
