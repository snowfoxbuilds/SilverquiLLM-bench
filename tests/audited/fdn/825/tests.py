"""Audited tests for Sublime Epiphany (FDN — synthetic dir 825)."""
from __future__ import annotations
import pytest
from card_impl import SublimeEpiphany
from engine.card import Instant
from engine.types import ManaCost


@pytest.mark.basic
class TestSublimeEpiphanyBasic:
    def test_is_instant(self) -> None:
        card = SublimeEpiphany()
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = SublimeEpiphany()
        assert card.name == "Sublime Epiphany"

    def test_mana_cost(self) -> None:
        card = SublimeEpiphany()
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")


@pytest.mark.ability
class TestSublimeEpiphanyModes:
    def test_has_five_modes(self) -> None:
        card = SublimeEpiphany()
        modes = card.get_modes()
        assert len(modes) == 5

    def test_mode_names(self) -> None:
        card = SublimeEpiphany()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Counter Spell" in names
        assert "Draw" in names
        assert "Bounce" in names


@pytest.mark.rules
class TestSublimeEpiphanyResolve:
    def test_draw_mode_draws_card(self) -> None:
        """Mode 3: target player draws a card."""
        from tests.test_utils import create_game
        from engine.card import CardImpl
        from engine.types import Zone
        game = create_game()
        p = game.players[0]
        card = SublimeEpiphany(owner=p)
        card.controller = p
        card.chosen_modes = [3]
        # Stock library
        lib_card = CardImpl(name="DrawMe")
        lib_card.owner = p
        p.zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(p.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p.zones[Zone.HAND].get_all()) >= hand_before + 1
