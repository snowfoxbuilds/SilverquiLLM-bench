"""Tests for cards/foundations/artifacts.py — Artifact cards.

Verifies:
- Each artifact has the correct name, mana_cost, and card_types.
- Mana rocks have working get_mana_abilities().
- Equipment has the Equipment subtype and attached_to attribute.
- register_artifacts() registers all 10 artifacts in the registry.
"""

from __future__ import annotations

import pytest

from cards.foundations.artifacts import (
    AltarOfTheBrood,
    ArcaneSigNet,
    Bonesplitter,
    ElixirOfImmortality,
    MaskOfMemory,
    MindStone,
    RelicOfProgenitus,
    SolRing,
    SwiftfootBoots,
    WhispersilkCloak,
    register_artifacts,
)
from cards.registry import CardRegistry
from engine.card import Artifact, Creature, GameObject
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, ManaType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


def _make_game(
    *,
    p1_battlefield: list | None = None,
) -> tuple[GameState, DeterministicPlayer]:
    GameObject.reset_id_counter()
    p1 = _make_player("P1")
    p2 = _make_player("P2")
    game = GameState(players=[p1, p2])
    for obj in (p1_battlefield or []):
        obj.controller = p1
        obj.owner = p1
        game.get_battlefield(p1).add(obj)
    return game, p1


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


# ---------------------------------------------------------------------------
# Mana rocks
# ---------------------------------------------------------------------------

class TestSolRing:
    def test_name_and_cost(self):
        card = SolRing()
        assert card.name == "Sol Ring"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert CardType.ARTIFACT in card.card_types

    def test_mana_abilities(self):
        card = SolRing()
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1
        assert "{C}{C}" in abilities[0].description


class TestArcaneSigNet:
    def test_name_and_cost(self):
        card = ArcaneSigNet()
        assert card.name == "Arcane Signet"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types

    def test_mana_abilities(self):
        card = ArcaneSigNet()
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1


class TestMindStone:
    def test_name_and_cost(self):
        card = MindStone()
        assert card.name == "Mind Stone"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types

    def test_mana_abilities(self):
        card = MindStone()
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class TestBonesplitter:
    def test_name_and_cost(self):
        card = Bonesplitter()
        assert card.name == "Bonesplitter"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert "Equipment" in card.subtypes

    def test_equip_buff(self):
        bear = _make_creature()
        game, p1 = _make_game(p1_battlefield=[bear])
        equip = Bonesplitter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(equip)
        equip.equip(bear, game)
        game.effect_manager.apply_all(game)
        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 2  # unchanged


class TestSwiftfootBoots:
    def test_name_and_cost(self):
        card = SwiftfootBoots()
        assert card.name == "Swiftfoot Boots"
        assert "Equipment" in card.subtypes

    def test_equip_keywords(self):
        bear = _make_creature()
        game, p1 = _make_game(p1_battlefield=[bear])
        equip = SwiftfootBoots(owner=p1, controller=p1)
        game.get_battlefield(p1).add(equip)
        equip.equip(bear, game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in bear.keywords
        assert Keyword.HASTE in bear.keywords


class TestWhispersilkCloak:
    def test_name_and_cost(self):
        card = WhispersilkCloak()
        assert card.name == "Whispersilk Cloak"
        assert "Equipment" in card.subtypes

    def test_equip_hexproof(self):
        bear = _make_creature()
        game, p1 = _make_game(p1_battlefield=[bear])
        equip = WhispersilkCloak(owner=p1, controller=p1)
        game.get_battlefield(p1).add(equip)
        equip.equip(bear, game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in bear.keywords


class TestMaskOfMemory:
    def test_name_and_cost(self):
        card = MaskOfMemory()
        assert card.name == "Mask of Memory"
        assert "Equipment" in card.subtypes


# ---------------------------------------------------------------------------
# Utility artifacts
# ---------------------------------------------------------------------------

class TestAltarOfTheBrood:
    def test_name_and_cost(self):
        card = AltarOfTheBrood()
        assert card.name == "Altar of the Brood"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert CardType.ARTIFACT in card.card_types


class TestElixirOfImmortality:
    def test_name_and_cost(self):
        card = ElixirOfImmortality()
        assert card.name == "Elixir of Immortality"
        assert card.mana_cost == ManaCost.parse("{1}")


class TestRelicOfProgenitus:
    def test_name_and_cost(self):
        card = RelicOfProgenitus()
        assert card.name == "Relic of Progenitus"
        assert card.mana_cost == ManaCost.parse("{1}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_artifacts_count(self):
        registry = CardRegistry()
        register_artifacts(registry)
        assert len(registry) == 10

    def test_registered_names(self):
        registry = CardRegistry()
        register_artifacts(registry)
        expected = {
            "Sol Ring", "Arcane Signet", "Mind Stone",
            "Bonesplitter", "Swiftfoot Boots", "Whispersilk Cloak",
            "Mask of Memory", "Altar of the Brood",
            "Elixir of Immortality", "Relic of Progenitus",
        }
        assert set(registry.list_all()) == expected
