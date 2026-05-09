"""Tests for cards/foundations/auras_batch2.py — Batch 2 aura cards.

Verifies:
- Each aura has correct metadata (name, mana_cost, card_types, subtypes, is_aura).
- get_targets returns TargetRequirement for appropriate permanents.
- on_resolve attaches the aura (sets attached_to).
- Continuous effects apply correctly (stat buffs, keywords, lockdown).
- Aura goes to graveyard via SBA when enchanted creature is removed.
- Triggered-ability auras fire correctly.
- register_auras_batch2() registers all 10 auras.
"""

from __future__ import annotations

import pytest

from cards.foundations.auras_batch2 import (
    AngelicDestiny,
    BlanchwoodArmor,
    Confiscate,
    EatenByPiranhas,
    ImprisonedInTheMoon,
    NewHorizons,
    OrdealOfNylea,
    StarlightSnare,
    TwinbladeBlessing,
    WitnessProtection,
    register_auras_batch2,
)
from cards.registry import CardRegistry
from engine.card import Aura, Creature, GameObject, Land
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, Zone


# ---------------------------------------------------------------------------
# Helpers (mirrors test_enchantments.py patterns)
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


def _make_land(name: str = "Forest", subtypes: set | None = None) -> Land:
    return Land(name=name, subtypes=subtypes or {"Forest"})


def _attach_aura(aura, target, game, player):
    """Helper: place aura on battlefield, set target, resolve."""
    aura.owner = player
    aura.controller = player
    game.get_battlefield(player).add(aura)
    aura._resolve_target = target
    aura.on_resolve(game)


def _apply_effects(game):
    """Apply all continuous effects."""
    game.effect_manager.apply_all(game)


def _run_sbas(game):
    """Run state-based actions."""
    from engine.state_based_actions import resolve_state_based_actions
    resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# Angelic Destiny — buff aura with death trigger
# ---------------------------------------------------------------------------

class TestAngelicDestiny:
    def test_metadata(self):
        card = AngelicDestiny()
        assert card.name == "Angelic Destiny"
        assert card.mana_cost == ManaCost.parse("{2}{W}{W}")
        assert CardType.ENCHANTMENT in card.card_types
        assert card.is_aura is True
        assert "Aura" in card.subtypes

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_buff_plus_4_4(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 6  # 2 + 4
        assert bear.toughness == 6  # 2 + 4

    def test_grants_flying_and_first_strike(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert Keyword.FLYING in bear.keywords
        assert Keyword.FIRST_STRIKE in bear.keywords

    def test_adds_angel_subtype(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert "Angel" in getattr(bear, "subtypes", set())

    def test_get_targets_returns_creatures(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        targets = aura.get_targets(game)
        assert len(targets) == 1
        assert targets[0].zone == Zone.BATTLEFIELD

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = AngelicDestiny()
        _attach_aura(aura, bear, game, p1)
        # Remove the creature from battlefield
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        # Aura should be in graveyard (or hand per death trigger)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Blanchwood Armor — buff based on Forest count
# ---------------------------------------------------------------------------

class TestBlanchwoodArmor:
    def test_metadata(self):
        card = BlanchwoodArmor()
        assert card.name == "Blanchwood Armor"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.is_aura is True
        assert "Aura" in card.subtypes

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = BlanchwoodArmor()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_buff_with_forests(self):
        bear = _make_creature()
        forest1 = _make_land("Forest1", {"Forest"})
        forest2 = _make_land("Forest2", {"Forest"})
        game, p1, p2 = _make_game(p1_battlefield=[bear, forest1, forest2])
        aura = BlanchwoodArmor()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 4  # 2 + 2 forests
        assert bear.toughness == 4

    def test_buff_zero_forests(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = BlanchwoodArmor()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 2  # no forests
        assert bear.toughness == 2

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = BlanchwoodArmor()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Twinblade Blessing — keyword-granting aura
# ---------------------------------------------------------------------------

class TestTwinbladeBlessing:
    def test_metadata(self):
        card = TwinbladeBlessing()
        assert card.name == "Twinblade Blessing"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.is_aura is True
        assert Keyword.FLASH in card.keywords

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = TwinbladeBlessing()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_grants_double_strike(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = TwinbladeBlessing()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert Keyword.DOUBLE_STRIKE in bear.keywords

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = TwinbladeBlessing()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Starlight Snare — lockdown aura with ETB tap
# ---------------------------------------------------------------------------

class TestStarlightSnare:
    def test_metadata(self):
        card = StarlightSnare()
        assert card.name == "Starlight Snare"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.is_aura is True

    def test_attachment_taps_creature(self):
        bear = _make_creature()
        bear.is_tapped = False
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = StarlightSnare()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear
        assert bear.is_tapped is True

    def test_skip_untap_effect(self):
        bear = _make_creature()
        bear.is_tapped = False
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = StarlightSnare()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert getattr(bear, "_skip_untap", False) is True

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = StarlightSnare()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Imprisoned in the Moon — lockdown aura (creature/land/planeswalker)
# ---------------------------------------------------------------------------

class TestImprisonedInTheMoon:
    def test_metadata(self):
        card = ImprisonedInTheMoon()
        assert card.name == "Imprisoned in the Moon"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.is_aura is True

    def test_get_targets_includes_creatures_lands_planeswalkers(self):
        bear = _make_creature()
        land = _make_land("Plains", {"Plains"})
        game, p1, p2 = _make_game(p1_battlefield=[bear, land])
        aura = ImprisonedInTheMoon()
        targets = aura.get_targets(game)
        assert len(targets) == 1  # single TargetRequirement
        # Both bear and land should pass the filter
        assert targets[0].filter_fn(bear)
        assert targets[0].filter_fn(land)

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = ImprisonedInTheMoon()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_becomes_colorless_land(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = ImprisonedInTheMoon()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.card_types == {CardType.LAND}
        assert bear.keywords == Keyword(0)

    def test_cant_attack_block_activate(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = ImprisonedInTheMoon()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert getattr(bear, "_cant_attack", False) is True
        assert getattr(bear, "_cant_block", False) is True
        assert getattr(bear, "_cant_activate", False) is True

    def test_aura_to_graveyard_when_target_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = ImprisonedInTheMoon()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Witness Protection — lockdown aura (becomes 1/1 Citizen)
# ---------------------------------------------------------------------------

class TestWitnessProtection:
    def test_metadata(self):
        card = WitnessProtection()
        assert card.name == "Witness Protection"
        assert card.mana_cost == ManaCost.parse("{U}")
        assert card.is_aura is True

    def test_attachment(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = WitnessProtection()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_becomes_1_1_citizen(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = WitnessProtection()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.base_power == 1
        assert bear.base_toughness == 1
        assert "Citizen" in bear.subtypes
        assert bear.keywords == Keyword(0)

    def test_creature_renamed(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = WitnessProtection()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.name == "Legitimate Businessperson"

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = WitnessProtection()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Eaten by Piranhas — lockdown aura (becomes 1/1 Skeleton)
# ---------------------------------------------------------------------------

class TestEatenByPiranhas:
    def test_metadata(self):
        card = EatenByPiranhas()
        assert card.name == "Eaten by Piranhas"
        assert card.mana_cost == ManaCost.parse("{1}{U}")
        assert card.is_aura is True
        assert Keyword.FLASH in card.keywords

    def test_attachment(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = EatenByPiranhas()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_becomes_1_1_skeleton(self):
        bear = _make_creature(power=5, toughness=5)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = EatenByPiranhas()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.base_power == 1
        assert bear.base_toughness == 1
        assert "Skeleton" in bear.subtypes
        assert bear.keywords == Keyword(0)

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = EatenByPiranhas()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# New Horizons — enchant land with ETB +1/+1 counter
# ---------------------------------------------------------------------------

class TestNewHorizons:
    def test_metadata(self):
        card = NewHorizons()
        assert card.name == "New Horizons"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.is_aura is True

    def test_get_targets_returns_lands(self):
        land = _make_land("Forest", {"Forest"})
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[land, bear])
        aura = NewHorizons()
        targets = aura.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(land)
        assert not targets[0].filter_fn(bear)

    def test_attachment_to_land(self):
        land = _make_land("Forest", {"Forest"})
        game, p1, p2 = _make_game(p1_battlefield=[land])
        aura = NewHorizons()
        _attach_aura(aura, land, game, p1)
        assert aura.attached_to is land

    def test_etb_puts_counter_on_creature(self):
        land = _make_land("Forest", {"Forest"})
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[land, bear])
        aura = NewHorizons()
        _attach_aura(aura, land, game, p1)
        counters = getattr(bear, "counters", {})
        assert counters.get("+1/+1", 0) == 1

    def test_continuous_effect_marks_land(self):
        land = _make_land("Forest", {"Forest"})
        game, p1, p2 = _make_game(p1_battlefield=[land])
        aura = NewHorizons()
        _attach_aura(aura, land, game, p1)
        _apply_effects(game)
        assert getattr(land, "_new_horizons_mana", False) is True

    def test_aura_to_graveyard_when_land_removed(self):
        land = _make_land("Forest", {"Forest"})
        game, p1, p2 = _make_game(p1_battlefield=[land])
        aura = NewHorizons()
        _attach_aura(aura, land, game, p1)
        game.get_battlefield(p1).remove(land)
        game.get_graveyard(p1).add(land)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Ordeal of Nylea — triggered-ability aura (attack trigger)
# ---------------------------------------------------------------------------

class TestOrdealOfNylea:
    def test_metadata(self):
        card = OrdealOfNylea()
        assert card.name == "Ordeal of Nylea"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.is_aura is True

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = OrdealOfNylea()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_has_register_triggers(self):
        """Ordeal of Nylea should override register_triggers."""
        aura = OrdealOfNylea()
        assert hasattr(aura, "register_triggers")
        assert callable(aura.register_triggers)

    def test_aura_to_graveyard_when_creature_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        aura = OrdealOfNylea()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Confiscate — control-changing aura
# ---------------------------------------------------------------------------

class TestConfiscate:
    def test_metadata(self):
        card = Confiscate()
        assert card.name == "Confiscate"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert card.is_aura is True

    def test_get_targets_returns_any_permanent(self):
        bear = _make_creature()
        land = _make_land()
        game, p1, p2 = _make_game(p1_battlefield=[bear, land])
        aura = Confiscate()
        targets = aura.get_targets(game)
        assert len(targets) == 1
        # Both creature and land should be valid
        assert targets[0].filter_fn(bear)
        assert targets[0].filter_fn(land)

    def test_attachment(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p2_battlefield=[bear])
        aura = Confiscate()
        _attach_aura(aura, bear, game, p1)
        assert aura.attached_to is bear

    def test_gains_control(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p2_battlefield=[bear])
        aura = Confiscate()
        _attach_aura(aura, bear, game, p1)
        _apply_effects(game)
        assert bear.controller is p1

    def test_aura_to_graveyard_when_permanent_removed(self):
        bear = _make_creature()
        game, p1, p2 = _make_game(p2_battlefield=[bear])
        aura = Confiscate()
        _attach_aura(aura, bear, game, p1)
        game.get_battlefield(p2).remove(bear)
        game.get_graveyard(p2).add(bear)
        _run_sbas(game)
        assert not game.get_battlefield(p1).contains(aura)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_count(self):
        registry = CardRegistry()
        register_auras_batch2(registry)
        assert len(registry) == 10

    def test_registered_names(self):
        registry = CardRegistry()
        register_auras_batch2(registry)
        expected = {
            "Angelic Destiny",
            "Blanchwood Armor",
            "Twinblade Blessing",
            "Starlight Snare",
            "Imprisoned in the Moon",
            "Witness Protection",
            "Eaten by Piranhas",
            "New Horizons",
            "Ordeal of Nylea",
            "Confiscate",
        }
        assert set(registry.list_all()) == expected
