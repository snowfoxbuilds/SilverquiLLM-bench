"""Audited tests for New Horizons (FDN collector number 557)."""

from __future__ import annotations
import pytest
from card_impl import NewHorizons
from engine.card import Aura, Creature
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestNewHorizonsBasic:
    def test_is_aura(self) -> None:
        card = NewHorizons(name="New Horizons", owner=None)
        assert isinstance(card, Aura)

    def test_name(self) -> None:
        card = NewHorizons(name="New Horizons", owner=None)
        assert card.name == "New Horizons"

    def test_attach_sets_target(self) -> None:
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        aura = NewHorizons(name="New Horizons", owner=game.players[0])
        aura.controller = game.players[0]
        set_board_state(game, 0, battlefield=[creature, aura])
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        assert aura.attached_to is creature
