"""Audited tests for Boros Charm (FDN — synthetic dir 823)."""
from __future__ import annotations
import pytest
from card_impl import BorosCharm
from engine.card import Instant
from engine.types import ManaCost


@pytest.mark.basic
class TestBorosCharmBasic:
    def test_is_instant(self) -> None:
        card = BorosCharm()
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = BorosCharm()
        assert card.name == "Boros Charm"

    def test_mana_cost(self) -> None:
        card = BorosCharm()
        assert card.mana_cost == ManaCost.parse("{R}{W}")


@pytest.mark.ability
class TestBorosCharmModes:
    def test_has_three_modes(self) -> None:
        card = BorosCharm()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_mode_names(self) -> None:
        card = BorosCharm()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Damage" in names
        assert "Indestructible" in names
        assert "Double Strike" in names


@pytest.mark.rules
class TestBorosCharmResolve:
    def test_damage_mode_deals_four_to_player(self) -> None:
        """Mode 0: deal 4 damage to target player."""
        from tests.test_utils import create_game
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = BorosCharm(owner=p0)
        card.controller = p0
        card.chosen_mode = 0
        card.chosen_targets = [p1]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before - 4
