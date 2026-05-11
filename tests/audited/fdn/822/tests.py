"""Audited tests for Abzan Charm (FDN — synthetic dir 822)."""
from __future__ import annotations
import pytest
from card_impl import AbzanCharm
from engine.card import Instant
from engine.types import ManaCost


@pytest.mark.basic
class TestAbzanCharmBasic:
    def test_is_instant(self) -> None:
        card = AbzanCharm()
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = AbzanCharm()
        assert card.name == "Abzan Charm"

    def test_mana_cost(self) -> None:
        card = AbzanCharm()
        assert card.mana_cost == ManaCost.parse("{W}{B}{G}")


@pytest.mark.ability
class TestAbzanCharmModes:
    def test_has_three_modes(self) -> None:
        card = AbzanCharm()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_mode_names(self) -> None:
        card = AbzanCharm()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Exile" in names
        assert "Draw" in names
        assert "Counters" in names


@pytest.mark.rules
class TestAbzanCharmResolve:
    def test_draw_mode_draws_two_loses_two_life(self) -> None:
        """Mode 1: draw 2 cards, lose 2 life."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import CardImpl
        from engine.types import Zone
        game = create_game()
        p = game.players[0]
        card = AbzanCharm(owner=p)
        card.controller = p
        card.chosen_mode = 1
        # Stock library so draw works
        for i in range(3):
            c = CardImpl(name=f"Draw{i}")
            c.owner = p
            p.zones[Zone.LIBRARY].add(c)
        life_before = p.life
        hand_before = len(p.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert p.life == life_before - 2
        assert len(p.zones[Zone.HAND].get_all()) >= hand_before + 2
