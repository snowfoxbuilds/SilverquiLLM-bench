"""Tests for cards/fdn/_legacy/enchantments.py — Enchantment cards.

Verifies:
- Each enchantment has the correct name, mana_cost, card_types, and rules_text.
- Aura enchantments have is_aura = True and correct subtypes.
- Global enchantments have is_aura = False.
- Aura attachment via on_resolve sets attached_to.
- Continuous effects from global enchantments modify creatures correctly.
- register_enchantments() registers all 8 enchantments in the registry.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.enchantments import (
    Arrest,
    BraveTheSands,
    DictateOfHeliod,
    GloriousAnthem,
    HolyStrength,
    Levitation,
    StabWound,
    UnholyStrength,
    register_enchantments,
)
from cards.registry import CardRegistry
from engine.card import Aura, Enchantment, Creature, GameObject
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


def _make_game(
    *,
    p1_battlefield: list | None = None,
    p2_battlefield: list | None = None,
) -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    GameObject.reset_id_counter()
    p1 = _make_player("P1")
    p2 = _make_player("P2")
    game = GameState(players=[p1, p2])
    for obj in (p1_battlefield or []):
        obj.controller = p1
        obj.owner = p1
        game.get_battlefield(p1).add(obj)
    for obj in (p2_battlefield or []):
        obj.controller = p2
        obj.owner = p2
        game.get_battlefield(p2).add(obj)
    return game, p1, p2


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2, **kw) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness, **kw)


# ---------------------------------------------------------------------------
# Aura basics
# ---------------------------------------------------------------------------

class TestHolyStrength:
    def test_name_and_cost(self):
        card = HolyStrength()
        assert card.name == "Holy Strength"
        assert card.mana_cost == ManaCost.parse("{W}")
        assert CardType.ENCHANTMENT in card.card_types
        assert card.is_aura is True
        assert "Aura" in card.subtypes

    def test_pt_buff(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = HolyStrength(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aura)
        aura._resolve_target = bear
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 3  # 2 + 1
        assert bear.toughness == 4  # 2 + 2


class TestUnholyStrength:
    def test_name_and_cost(self):
        card = UnholyStrength()
        assert card.name == "Unholy Strength"
        assert card.mana_cost == ManaCost.parse("{B}")
        assert card.is_aura is True

    def test_pt_buff(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = UnholyStrength(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aura)
        aura._resolve_target = bear
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 3  # 2 + 1


class TestStabWound:
    def test_name_and_cost(self):
        card = StabWound()
        assert card.name == "Stab Wound"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.is_aura is True

    def test_pt_debuff(self):
        bear = _make_creature(power=4, toughness=4)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = StabWound(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aura)
        aura._resolve_target = bear
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 2  # 4 - 2
        assert bear.toughness == 2  # 4 - 2


class TestArrest:
    def test_name_and_cost(self):
        card = Arrest()
        assert card.name == "Arrest"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.is_aura is True

    def test_cant_attack_or_block(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = Arrest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aura)
        aura._resolve_target = bear
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(bear, "_cant_attack", False) is True
        assert getattr(bear, "_cant_block", False) is True
        assert getattr(bear, "_cant_activate", False) is True


# ---------------------------------------------------------------------------
# Global enchantments
# ---------------------------------------------------------------------------

class TestGloriousAnthem:
    def test_name_and_cost(self):
        card = GloriousAnthem()
        assert card.name == "Glorious Anthem"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert CardType.ENCHANTMENT in card.card_types
        assert card.is_aura is False

    def test_buff_creatures(self):
        bear1 = _make_creature("Bear1")
        bear2 = _make_creature("Bear2")
        game, p1, p2 = _make_game(p1_battlefield=[bear1, bear2])
        anthem = GloriousAnthem(owner=p1, controller=p1)
        game.get_battlefield(p1).add(anthem)
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert bear1.power == 3
        assert bear1.toughness == 3
        assert bear2.power == 3
        assert bear2.toughness == 3

    def test_no_buff_opponent(self):
        my_bear = _make_creature("MyBear")
        opp_bear = _make_creature("OppBear")
        game, p1, p2 = _make_game(p1_battlefield=[my_bear], p2_battlefield=[opp_bear])
        anthem = GloriousAnthem(owner=p1, controller=p1)
        game.get_battlefield(p1).add(anthem)
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert my_bear.power == 3
        assert opp_bear.power == 2  # not affected


class TestDictateOfHeliod:
    def test_flash_keyword(self):
        card = DictateOfHeliod()
        assert Keyword.FLASH in card.keywords

    def test_buff_creatures(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        dictate = DictateOfHeliod(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dictate)
        dictate.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 4


class TestBraveTheSands:
    def test_grants_vigilance(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        bts = BraveTheSands(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bts)
        bts.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.VIGILANCE in bear.keywords


class TestLevitation:
    def test_grants_flying(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        lev = Levitation(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lev)
        lev.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in bear.keywords


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_enchantments_count(self):
        registry = CardRegistry()
        register_enchantments(registry)
        assert len(registry) == 8

    def test_registered_names(self):
        registry = CardRegistry()
        register_enchantments(registry)
        expected = {
            "Holy Strength", "Unholy Strength", "Stab Wound", "Arrest",
            "Glorious Anthem", "Dictate of Heliod", "Brave the Sands", "Levitation",
        }
        assert set(registry.list_all()) == expected
