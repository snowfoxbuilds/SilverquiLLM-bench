"""Audited tests for Gilded Lotus (FDN collector number 725)."""
from __future__ import annotations
import pytest
from card_impl import GildedLotus
from engine.card import Artifact
from engine.types import ManaType, CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGildedLotusBasic:
    def test_is_artifact(self) -> None:
        card = GildedLotus(name="Gilded Lotus", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types

@pytest.mark.ability
class TestGildedLotusAbility:
    def test_taps_for_three_mana(self) -> None:
        """Gilded Lotus produces exactly 3 mana."""
        game = create_game()
        card = GildedLotus(name="Gilded Lotus", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 3
    def test_cannot_tap_when_already_tapped(self) -> None:
        game = create_game()
        card = GildedLotus(name="Gilded Lotus", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        result = abilities[0].cost(game, card)
        assert result is False
