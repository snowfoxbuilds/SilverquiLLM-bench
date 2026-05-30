"""Tests for SOS 4 — Together as One (converge)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(player: Any, n: int) -> None:
    for i in range(n):
        c = Creature(
            name=f"Lib{i}",
            owner=player,
            controller=player,
            base_power=1,
            base_toughness=1,
        )
        player.zones[Zone.LIBRARY].add(c)


class TestTogetherProperties:
    def test_name(self) -> None:
        assert TogetherAsOne().name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne().mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        assert CardType.SORCERY in TogetherAsOne().card_types


class TestTogetherConverge:
    def test_zero_colors_does_nothing(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _fill_library(p1, 3)
        together = TogetherAsOne(owner=p1, controller=p1)
        together.colors_spent = 0  # type: ignore[attr-defined]
        together.chosen_targets = [p1, p2]  # type: ignore[attr-defined]
        together.on_resolve(game)
        assert p2.life == 20
        assert p1.life == 20
        assert len(p1.zones[Zone.LIBRARY]) == 3  # no draws

    def test_direct_resolve_two_colors(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _fill_library(p1, 5)
        together = TogetherAsOne(owner=p1, controller=p1)
        together.colors_spent = 2  # type: ignore[attr-defined]
        together.chosen_targets = [p1, p2]  # type: ignore[attr-defined]
        together.on_resolve(game)
        # X = 2: p1 draws 2, p2 takes 2 damage, p1 gains 2 life.
        assert len(p1.zones[Zone.LIBRARY]) == 3
        assert p2.life == 18
        assert p1.life == 22

    def test_cast_through_engine_counts_colors(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _fill_library(p1, 5)
        together = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[together],
            mana={ManaType.RED: 2, ManaType.WHITE: 2, ManaType.BLUE: 2},
        )
        # Targets: p1 draws, p2 takes damage.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # X = 3 distinct colors of mana spent.
        assert len(p1.zones[Zone.LIBRARY]) == 2  # drew 3
        assert p2.life == 17
        assert p1.life == 23
        assert game.get_graveyard(p1).contains(together)
