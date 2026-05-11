"""Audited tests for Collective Brutality (FDN — synthetic dir 828)."""
from __future__ import annotations
import pytest
from card_impl import CollectiveBrutality
from engine.card import Sorcery
from engine.types import ManaCost


@pytest.mark.basic
class TestCollectiveBrutalityBasic:
    def test_is_sorcery(self) -> None:
        card = CollectiveBrutality()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = CollectiveBrutality()
        assert card.name == "Collective Brutality"

    def test_mana_cost(self) -> None:
        card = CollectiveBrutality()
        assert card.mana_cost == ManaCost.parse("{1}{B}")


@pytest.mark.ability
class TestCollectiveBrutalityModes:
    def test_has_three_modes(self) -> None:
        card = CollectiveBrutality()
        modes = card.get_modes()
        assert len(modes) == 3

    def test_mode_names(self) -> None:
        card = CollectiveBrutality()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Discard" in names
        assert "Shrink" in names
        assert "Drain" in names


@pytest.mark.rules
class TestCollectiveBrutalityResolve:
    def test_drain_mode_loses_life_and_gains_life(self) -> None:
        """Mode 2: target opponent loses 2 life and you gain 2 life."""
        from tests.test_utils import create_game
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = CollectiveBrutality(owner=p0)
        card.controller = p0
        card.chosen_modes = [2]
        card.chosen_targets = [p1]
        p0_life_before = p0.life
        p1_life_before = p1.life
        card.on_resolve(game)
        assert p1.life == p1_life_before - 2
        assert p0.life == p0_life_before + 2
