"""Audited tests for Whispersilk Cloak (FDN — synthetic dir 805)."""
from __future__ import annotations
import pytest
from card_impl import WhispersilkCloak
from engine.card import Artifact, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestWhispersilkCloakBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(WhispersilkCloak(name="Whispersilk Cloak", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in WhispersilkCloak(name="Whispersilk Cloak", owner=None).subtypes

@pytest.mark.ability
class TestWhispersilkCloakAbility:
    def test_grants_hexproof(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = WhispersilkCloak(name="Whispersilk Cloak", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in c.keywords
    def test_cant_be_blocked(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = WhispersilkCloak(name="Whispersilk Cloak", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert getattr(c, "_cant_be_blocked", False)
