"""Audited tests for FDN 87 — Goblin Boarders."""

from __future__ import annotations

from card_impl import GoblinBoarders
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestGoblinBoardersBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = GoblinBoarders(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GoblinBoarders(owner=None)
        assert card.name == "Goblin Boarders"

    def test_mana_cost(self) -> None:
        card = GoblinBoarders(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")

    def test_power_toughness(self) -> None:
        card = GoblinBoarders(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = GoblinBoarders(owner=None)
        assert "Goblin" in card.subtypes
        assert "Pirate" in card.subtypes


class TestGoblinBoardersRaid:
    """Raid — enters with a +1/+1 counter if attacked this turn."""

    def test_gets_counter_when_attacked_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinBoarders(owner=p1, controller=p1)
        game.attacked_this_turn = True
        card.on_resolve(game)
        counters = getattr(card, "counters", {})
        assert counters.get("+1/+1", 0) >= 1

    def test_no_counter_when_no_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinBoarders(owner=p1, controller=p1)
        game.attacked_this_turn = False
        card.on_resolve(game)
        counters = getattr(card, "counters", {})
        assert counters.get("+1/+1", 0) == 0

    def test_raid_checks_controller_attacked(self) -> None:
        """Raid can check controller.attacked_this_turn as fallback."""
        game = create_game()
        p1 = game.players[0]
        card = GoblinBoarders(owner=p1, controller=p1)
        game.attacked_this_turn = False
        p1.attacked_this_turn = True
        card.on_resolve(game)
        counters = getattr(card, "counters", {})
        assert counters.get("+1/+1", 0) >= 1
