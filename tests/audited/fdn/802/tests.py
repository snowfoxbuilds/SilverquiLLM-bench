"""Audited tests for Mind Stone (FDN — synthetic dir 802)."""
from __future__ import annotations
import pytest
from card_impl import MindStone
from engine.card import Artifact
from engine.types import ManaType, CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestMindStoneBasic:
    def test_is_artifact(self) -> None:
        card = MindStone(name="Mind Stone", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types

@pytest.mark.ability
class TestMindStoneAbility:
    def test_taps_for_one_colorless(self) -> None:
        """Mind Stone taps for exactly 1 colorless mana."""
        game = create_game()
        card = MindStone(name="Mind Stone", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 1
    def test_cannot_tap_when_already_tapped(self) -> None:
        game = create_game()
        card = MindStone(name="Mind Stone", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        result = abilities[0].cost(game, card)
        assert result is False
    def test_tapping_sets_tapped_flag(self) -> None:
        game = create_game()
        card = MindStone(name="Mind Stone", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        assert not card.is_tapped
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert card.is_tapped
