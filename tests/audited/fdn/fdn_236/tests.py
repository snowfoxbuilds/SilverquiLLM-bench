"""Audited tests for FDN 236 — Wildwood Scourge."""

from __future__ import annotations

from card_impl import WildwoodScourge
from engine.card import Creature
from engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestWildwoodScourgeBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.name == "Wildwood Scourge"

    def test_mana_cost(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{G}")

    def test_power_toughness(self) -> None:
        card = WildwoodScourge(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 0

    def test_subtypes(self) -> None:
        card = WildwoodScourge(owner=None)
        assert "Hydra" in card.subtypes


class TestWildwoodScourgeETB:
    """Enters with X +1/+1 counters."""

    def test_enters_with_x_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scourge = WildwoodScourge(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scourge)
        scourge.x_value = 3
        scourge.on_resolve(game)
        assert scourge.plus_one_counters == 3

    def test_x_zero_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scourge = WildwoodScourge(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scourge)
        scourge.x_value = 0
        scourge.on_resolve(game)
        assert getattr(scourge, "plus_one_counters", 0) == 0

