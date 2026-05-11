"""Audited tests for Austere Command (FDN — synthetic dir 827)."""
from __future__ import annotations
import pytest
from card_impl import AustereCommand
from engine.card import Sorcery
from engine.types import ManaCost


@pytest.mark.basic
class TestAustereCommandBasic:
    def test_is_sorcery(self) -> None:
        card = AustereCommand()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = AustereCommand()
        assert card.name == "Austere Command"

    def test_mana_cost(self) -> None:
        card = AustereCommand()
        assert card.mana_cost == ManaCost.parse("{4}{W}{W}")


@pytest.mark.ability
class TestAustereCommandModes:
    def test_has_four_modes(self) -> None:
        card = AustereCommand()
        modes = card.get_modes()
        assert len(modes) == 4

    def test_mode_names(self) -> None:
        card = AustereCommand()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Artifacts" in names
        assert "Enchantments" in names


@pytest.mark.rules
class TestAustereCommandResolve:
    def test_destroy_enchantments_mode(self) -> None:
        """Mode 1: destroy all enchantments."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Enchantment
        game = create_game()
        p = game.players[0]
        ench = Enchantment(name="TestEnch", owner=p)
        ench.controller = p
        set_board_state(game, 0, battlefield=[ench])
        card = AustereCommand(owner=p)
        card.controller = p
        card.chosen_modes = [1]
        card.on_resolve(game)
        bf = game.get_battlefield(p)
        assert not bf.contains(ench)
