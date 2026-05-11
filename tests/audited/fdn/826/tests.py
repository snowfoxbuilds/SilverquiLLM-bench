"""Audited tests for Dromoka's Command (FDN — synthetic dir 826)."""
from __future__ import annotations
import pytest
from card_impl import DromokasCommand
from engine.card import Sorcery
from engine.types import ManaCost


@pytest.mark.basic
class TestDromokasCommandBasic:
    def test_is_sorcery(self) -> None:
        card = DromokasCommand()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = DromokasCommand()
        assert card.name == "Dromoka's Command"

    def test_mana_cost(self) -> None:
        card = DromokasCommand()
        assert card.mana_cost == ManaCost.parse("{G}{W}")


@pytest.mark.ability
class TestDromokasCommandModes:
    def test_has_four_modes(self) -> None:
        card = DromokasCommand()
        modes = card.get_modes()
        assert len(modes) == 4

    def test_mode_names(self) -> None:
        card = DromokasCommand()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Counter" in names
        assert "Fight" in names


@pytest.mark.rules
class TestDromokasCommandResolve:
    def test_counter_mode_adds_plus_one_counter(self) -> None:
        """Mode 0: put a +1/+1 counter on target creature."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        set_board_state(game, 0, battlefield=[creature])
        card = DromokasCommand(owner=p)
        card.controller = p
        card.chosen_modes = [0]
        card.chosen_targets = [creature]
        counters_before = creature.plus_one_counters
        card.on_resolve(game)
        assert creature.plus_one_counters == counters_before + 1
