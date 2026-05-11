"""Audited tests for Arcane Signet (FDN — synthetic dir 801)."""
from __future__ import annotations
import pytest
from card_impl import ArcaneSigNet
from engine.card import Artifact
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestArcaneSignetBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(ArcaneSigNet(name="Arcane Signet", owner=None), Artifact)

@pytest.mark.ability
class TestArcaneSignetAbility:
    def test_taps_for_mana(self) -> None:
        game = create_game()
        card = ArcaneSigNet(name="Arcane Signet", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) >= 1
