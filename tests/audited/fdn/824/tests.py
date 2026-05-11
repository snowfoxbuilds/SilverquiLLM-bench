"""Audited tests for Prismari Command (FDN — synthetic dir 824)."""
from __future__ import annotations
import pytest
from card_impl import PrismariCommand
from engine.card import Instant
from engine.types import ManaCost


@pytest.mark.basic
class TestPrismariCommandBasic:
    def test_is_instant(self) -> None:
        card = PrismariCommand()
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = PrismariCommand()
        assert card.name == "Prismari Command"

    def test_mana_cost(self) -> None:
        card = PrismariCommand()
        assert card.mana_cost == ManaCost.parse("{1}{U}{R}")


@pytest.mark.ability
class TestPrismariCommandModes:
    def test_has_four_modes(self) -> None:
        card = PrismariCommand()
        modes = card.get_modes()
        assert len(modes) == 4

    def test_mode_names(self) -> None:
        card = PrismariCommand()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Damage" in names
        assert "Treasure" in names


@pytest.mark.rules
class TestPrismariCommandResolve:
    def test_treasure_mode_creates_token(self) -> None:
        """Mode 1: target player creates a Treasure token."""
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        card = PrismariCommand(owner=p)
        card.controller = p
        card.chosen_modes = [1]
        bf_before = len(game.get_battlefield(p).get_all())
        card.on_resolve(game)
        bf_after = game.get_battlefield(p).get_all()
        treasures = [c for c in bf_after if getattr(c, "name", "") == "Treasure"]
        assert len(treasures) >= 1
