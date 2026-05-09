"""Tests for cards/foundations/equipment.py — Equipment cards.

Verifies:
- Each equipment has correct metadata (name, mana_cost, card_types, subtypes).
- equip() attaches equipment to target creature.
- Equip activated ability costs mana and attaches equipment.
- Continuous effects apply correctly (stat boosts, keywords).
- Effects stop applying when creature is removed from battlefield.
- Equipment can be moved between creatures.
- Goldvein Pick combat damage trigger creates Treasure token.
- Adventuring Gear landfall trigger gives +2/+2.
- Celestial Armor ETB auto-attaches and grants hexproof/indestructible.
- Celestial Armor has flash keyword.
- register_equipment() registers all 7 equipment cards.
"""

from __future__ import annotations

import pytest

from cards.foundations.equipment import (
    AdventuringGear,
    BasiliskCollar,
    CelestialArmor,
    Fireshrieker,
    GoldveinPick,
    LeylineAxe,
    QuickDrawKatana,
    register_equipment,
)
from cards.registry import CardRegistry
from engine.card import Creature, GameObject, Land
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, ManaType


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


def _equip_on_battlefield(equip_cls, creature, game, player):
    """Place equipment on battlefield, equip to creature, return equipment."""
    equip = equip_cls()
    equip.owner = player
    equip.controller = player
    game.get_battlefield(player).add(equip)
    equip.equip(creature, game)
    return equip


def _place_on_battlefield(equip_cls, game, player):
    """Place equipment on battlefield without equipping, return equipment."""
    equip = equip_cls()
    equip.owner = player
    equip.controller = player
    game.get_battlefield(player).add(equip)
    if hasattr(equip, "register_triggers"):
        equip.register_triggers(game)
    return equip


def _apply_effects(game):
    """Apply all continuous effects."""
    game.effect_manager.apply_all(game)


def _run_sbas(game):
    from engine.state_based_actions import resolve_state_based_actions
    resolve_state_based_actions(game)


def _resolve_stack(game):
    """Resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ---------------------------------------------------------------------------
# Basilisk Collar
# ---------------------------------------------------------------------------

class TestBasiliskCollar:
    def test_metadata(self):
        card = BasiliskCollar()
        assert card.name == "Basilisk Collar"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_equip_sets_attached_to(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _equip_on_battlefield(BasiliskCollar, bear, game, p1)
        assert equip.attached_to is bear

    def test_grants_deathtouch_and_lifelink(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(BasiliskCollar, bear, game, p1)
        _apply_effects(game)
        assert Keyword.DEATHTOUCH in bear.keywords
        assert Keyword.LIFELINK in bear.keywords

    def test_no_keywords_after_creature_removed(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(BasiliskCollar, bear, game, p1)
        # Remove creature
        game.get_battlefield(p1).remove(bear)
        _apply_effects(game)
        assert Keyword.DEATHTOUCH not in bear.keywords
        assert Keyword.LIFELINK not in bear.keywords


# ---------------------------------------------------------------------------
# Fireshrieker
# ---------------------------------------------------------------------------

class TestFireshrieker:
    def test_metadata(self):
        card = Fireshrieker()
        assert card.name == "Fireshrieker"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_grants_double_strike(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(Fireshrieker, bear, game, p1)
        _apply_effects(game)
        assert Keyword.DOUBLE_STRIKE in bear.keywords

    def test_no_double_strike_after_creature_removed(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(Fireshrieker, bear, game, p1)
        game.get_battlefield(p1).remove(bear)
        _apply_effects(game)
        assert Keyword.DOUBLE_STRIKE not in bear.keywords


# ---------------------------------------------------------------------------
# Quick-Draw Katana
# ---------------------------------------------------------------------------

class TestQuickDrawKatana:
    def test_metadata(self):
        card = QuickDrawKatana()
        assert card.name == "Quick-Draw Katana"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_buff_during_controllers_turn(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(QuickDrawKatana, bear, game, p1)
        # Set active player to controller
        game.active_player_index = 0
        _apply_effects(game)
        assert bear.power == 4  # 2 + 2
        assert Keyword.FIRST_STRIKE in bear.keywords

    def test_no_buff_during_opponents_turn(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(QuickDrawKatana, bear, game, p1)
        # Set active player to opponent
        game.active_player_index = 1
        _apply_effects(game)
        assert bear.power == 2  # no buff
        assert Keyword.FIRST_STRIKE not in bear.keywords


# ---------------------------------------------------------------------------
# Goldvein Pick
# ---------------------------------------------------------------------------

class TestGoldveinPick:
    def test_metadata(self):
        card = GoldveinPick()
        assert card.name == "Goldvein Pick"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_stat_boost_plus_1_1(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(GoldveinPick, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 3  # 2 + 1
        assert bear.toughness == 3  # 2 + 1

    def test_combat_damage_trigger_creates_treasure(self):
        """When equipped creature deals combat damage to a player,
        a Treasure token should be created."""
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(GoldveinPick, game, p1)
        equip.equip(bear, game)
        # Count battlefield objects before trigger
        bf_before = len(game.get_battlefield(p1).get_all())
        # Fire combat damage event: equipped creature dealt combat damage to p2
        game.trigger_manager.fire_event(game, EventType.DEALS_DAMAGE, {
            "source": bear,
            "target": p2,
            "amount": 2,
            "is_combat": True,
        })
        _resolve_stack(game)
        # Should have one more object (Treasure token)
        bf_after = game.get_battlefield(p1).get_all()
        treasures = [obj for obj in bf_after if getattr(obj, "name", "") == "Treasure"]
        assert len(treasures) == 1, f"Expected 1 Treasure token, found {len(treasures)}"
        assert "Treasure" in treasures[0].subtypes

    def test_no_treasure_on_non_combat_damage(self):
        """Non-combat damage should not create a Treasure token."""
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(GoldveinPick, game, p1)
        equip.equip(bear, game)
        # Fire non-combat damage event
        game.trigger_manager.fire_event(game, EventType.DEALS_DAMAGE, {
            "source": bear,
            "target": p2,
            "amount": 2,
            "is_combat": False,
        })
        _resolve_stack(game)
        bf_after = game.get_battlefield(p1).get_all()
        treasures = [obj for obj in bf_after if getattr(obj, "name", "") == "Treasure"]
        assert len(treasures) == 0

    def test_no_treasure_when_different_creature_deals_damage(self):
        """Combat damage from a different creature should not create Treasure."""
        bear = _make_creature()
        other = _make_creature("Goblin")
        game, p1, p2 = _make_game(p1_battlefield=[bear, other])
        equip = _place_on_battlefield(GoldveinPick, game, p1)
        equip.equip(bear, game)
        # Fire damage event with wrong source
        game.trigger_manager.fire_event(game, EventType.DEALS_DAMAGE, {
            "source": other,
            "target": p2,
            "amount": 2,
            "is_combat": True,
        })
        _resolve_stack(game)
        bf_after = game.get_battlefield(p1).get_all()
        treasures = [obj for obj in bf_after if getattr(obj, "name", "") == "Treasure"]
        assert len(treasures) == 0


# ---------------------------------------------------------------------------
# Leyline Axe
# ---------------------------------------------------------------------------

class TestLeylineAxe:
    def test_metadata(self):
        card = LeylineAxe()
        assert card.name == "Leyline Axe"
        assert card.mana_cost == ManaCost.parse("{4}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_stat_boost_plus_1_1(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(LeylineAxe, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 3  # 2 + 1
        assert bear.toughness == 3  # 2 + 1

    def test_grants_double_strike_and_trample(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(LeylineAxe, bear, game, p1)
        _apply_effects(game)
        assert Keyword.DOUBLE_STRIKE in bear.keywords
        assert Keyword.TRAMPLE in bear.keywords


# ---------------------------------------------------------------------------
# Adventuring Gear
# ---------------------------------------------------------------------------

class TestAdventuringGear:
    def test_metadata(self):
        card = AdventuringGear()
        assert card.name == "Adventuring Gear"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_equip_sets_attached_to(self):
        """equip() method should set attached_to on the equipment."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _equip_on_battlefield(AdventuringGear, bear, game, p1)
        assert equip.attached_to is bear

    def test_landfall_trigger_gives_plus_2_2(self):
        """When a land enters under controller, equipped creature gets +2/+2."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(AdventuringGear, game, p1)
        equip.equip(bear, game)
        # Simulate a land entering the battlefield under controller
        land = Land(name="Mountain")
        land.owner = p1
        land.controller = p1
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": land,
            "controller": p1,
        })
        _resolve_stack(game)
        _apply_effects(game)
        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 4  # 2 + 2

    def test_landfall_no_trigger_for_opponent_land(self):
        """Landfall should not trigger for opponent's land."""
        bear = _make_creature()
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(AdventuringGear, game, p1)
        equip.equip(bear, game)
        # Simulate a land entering under opponent
        land = Land(name="Forest")
        land.owner = p2
        land.controller = p2
        game.get_battlefield(p2).add(land)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": land,
            "controller": p2,
        })
        _resolve_stack(game)
        _apply_effects(game)
        assert bear.power == 2  # no boost
        assert bear.toughness == 2

    def test_landfall_no_trigger_for_non_land(self):
        """Landfall should not trigger when a non-land permanent enters."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(AdventuringGear, game, p1)
        equip.equip(bear, game)
        # Simulate a creature entering (not a land)
        new_creature = _make_creature("Goblin")
        new_creature.owner = p1
        new_creature.controller = p1
        game.get_battlefield(p1).add(new_creature)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": new_creature,
            "controller": p1,
        })
        _resolve_stack(game)
        _apply_effects(game)
        assert bear.power == 2  # no boost


# ---------------------------------------------------------------------------
# Celestial Armor
# ---------------------------------------------------------------------------

class TestCelestialArmor:
    def test_metadata(self):
        card = CelestialArmor()
        assert card.name == "Celestial Armor"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert CardType.ARTIFACT in card.card_types
        assert "Equipment" in card.subtypes

    def test_has_flash(self):
        card = CelestialArmor()
        assert Keyword.FLASH in card.keywords

    def test_grants_flying(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(CelestialArmor, bear, game, p1)
        _apply_effects(game)
        assert Keyword.FLYING in bear.keywords

    def test_stat_boost_plus_2_0(self):
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        _equip_on_battlefield(CelestialArmor, bear, game, p1)
        _apply_effects(game)
        assert bear.power == 4  # 2 + 2
        assert bear.toughness == 2  # no toughness boost

    def test_etb_auto_attaches_to_creature(self):
        """When Celestial Armor enters the battlefield, its ETB trigger
        should auto-attach it to a creature on the controller's battlefield."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        armor = _place_on_battlefield(CelestialArmor, game, p1)
        # Fire ETB event for the armor itself
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": armor,
            "controller": p1,
        })
        _resolve_stack(game)
        assert armor.attached_to is bear

    def test_etb_grants_hexproof_and_indestructible(self):
        """ETB trigger should grant hexproof and indestructible to the
        creature it auto-attaches to."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        armor = _place_on_battlefield(CelestialArmor, game, p1)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": armor,
            "controller": p1,
        })
        _resolve_stack(game)
        _apply_effects(game)
        assert Keyword.HEXPROOF in bear.keywords
        assert Keyword.INDESTRUCTIBLE in bear.keywords

    def test_etb_also_registers_permanent_effects(self):
        """After ETB auto-attach, continuous effects (flying, +2/+0) should
        also apply."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        armor = _place_on_battlefield(CelestialArmor, game, p1)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {
            "permanent": armor,
            "controller": p1,
        })
        _resolve_stack(game)
        _apply_effects(game)
        assert Keyword.FLYING in bear.keywords
        assert bear.power == 4  # 2 + 2


# ---------------------------------------------------------------------------
# Cross-cutting equipment behavior
# ---------------------------------------------------------------------------

class TestEquipmentCrossCutting:
    def test_equip_to_different_creature(self):
        """Equipping to a second creature should move the attachment."""
        bear1 = _make_creature("Bear1")
        bear2 = _make_creature("Bear2")
        game, p1, _ = _make_game(p1_battlefield=[bear1, bear2])
        equip = _equip_on_battlefield(BasiliskCollar, bear1, game, p1)
        # Re-equip to bear2
        equip.equip(bear2, game)
        _apply_effects(game)
        assert equip.attached_to is bear2
        assert Keyword.DEATHTOUCH in bear2.keywords
        assert Keyword.LIFELINK in bear2.keywords

    def test_effects_stop_on_old_creature_after_reequip(self):
        """After re-equipping, the old creature should lose bonuses."""
        bear1 = _make_creature("Bear1")
        bear2 = _make_creature("Bear2")
        game, p1, _ = _make_game(p1_battlefield=[bear1, bear2])
        equip = _equip_on_battlefield(LeylineAxe, bear1, game, p1)
        _apply_effects(game)
        assert bear1.power == 3  # boosted
        # Re-equip to bear2
        equip.equip(bear2, game)
        _apply_effects(game)
        assert bear2.power == 3  # bear2 now boosted
        assert bear1.power == 2  # bear1 back to base

    def test_equipment_stays_on_battlefield_when_creature_dies(self):
        """When equipped creature dies, equipment should remain on battlefield."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _equip_on_battlefield(BasiliskCollar, bear, game, p1)
        # Kill the creature
        game.get_battlefield(p1).remove(bear)
        game.get_graveyard(p1).add(bear)
        assert game.get_battlefield(p1).contains(equip)


# ---------------------------------------------------------------------------
# Equip activated ability
# ---------------------------------------------------------------------------

class TestEquipActivatedAbility:
    def test_equipment_has_equip_ability(self):
        """Every equipment should expose an equip activated ability."""
        for cls in (BasiliskCollar, Fireshrieker, QuickDrawKatana,
                    GoldveinPick, LeylineAxe, AdventuringGear, CelestialArmor):
            equip = cls()
            abilities = equip.get_activated_abilities()
            assert len(abilities) >= 1, f"{cls.__name__} should have at least 1 activated ability"
            assert "equip" in abilities[0].description.lower(), (
                f"{cls.__name__} ability description should mention 'equip'"
            )

    def test_equip_ability_description_includes_cost(self):
        """Equip ability description should indicate the mana cost."""
        collar = BasiliskCollar()
        abilities = collar.get_activated_abilities()
        # Basilisk Collar has Equip {2}
        assert "{2}" in abilities[0].description

    def test_equip_ability_cost_requires_mana(self):
        """Equip ability cost should fail if controller has insufficient mana."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(BasiliskCollar, game, p1)
        abilities = equip.get_activated_abilities()
        ability = abilities[0]
        # Pool is empty — cost should fail
        result = ability.cost(game, equip)
        assert result is False, "Equip cost should fail with empty mana pool"

    def test_equip_ability_cost_succeeds_with_mana(self):
        """Equip ability cost should succeed if controller has enough mana."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(BasiliskCollar, game, p1)
        # Add enough mana (Equip {2})
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        abilities = equip.get_activated_abilities()
        ability = abilities[0]
        result = ability.cost(game, equip)
        assert result is True, "Equip cost should succeed with enough mana"

    def test_equip_ability_effect_attaches(self):
        """Equip ability effect should attach equipment to target creature."""
        bear = _make_creature()
        game, p1, _ = _make_game(p1_battlefield=[bear])
        equip = _place_on_battlefield(BasiliskCollar, game, p1)
        # Set current target (engine convention)
        equip._current_target = bear
        abilities = equip.get_activated_abilities()
        ability = abilities[0]
        ability.effect(game)
        assert equip.attached_to is bear


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestEquipmentRegistry:
    def test_register_equipment_all_seven(self):
        registry = CardRegistry()
        register_equipment(registry)
        expected = [
            "Basilisk Collar",
            "Fireshrieker",
            "Quick-Draw Katana",
            "Goldvein Pick",
            "Leyline Axe",
            "Adventuring Gear",
            "Celestial Armor",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_registry_creates_correct_instances(self):
        registry = CardRegistry()
        register_equipment(registry)
        card = registry.create_instance("Basilisk Collar")
        assert isinstance(card, BasiliskCollar)
        assert card.name == "Basilisk Collar"
