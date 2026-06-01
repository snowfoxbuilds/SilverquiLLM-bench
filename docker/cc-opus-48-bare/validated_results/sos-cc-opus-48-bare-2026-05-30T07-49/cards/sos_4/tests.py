"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(game, player, count: int) -> None:
    lib = game.get_library(player)
    for i in range(count):
        lib.add(Creature(name=f"f{i}", base_power=1, base_toughness=1))


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_colors_spent_defaults_to_zero(self) -> None:
        assert TogetherAsOne(owner=None).colors_spent == 0


class TestTogetherAsOneConverge:
    def test_triple_effect_with_three_colors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, p1, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, p2]

        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) - hand_before == 3
        assert p2.life == 20 - 3
        assert p1.life == 20 + 3

    def test_zero_colors_does_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, p1, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p1, p2]

        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == hand_before
        assert p2.life == 20
        assert p1.life == 20

    def test_real_cast_counts_distinct_colors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _fill_library(game, p1, 5)
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={
                ManaType.COLORLESS: 3,
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
            },
        )

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        # X = 3 (white, blue, black spent).
        assert isinstance(card.colors_spent, list)
        assert p2.life == 20 - 3
        assert p1.life == 20 + 3
