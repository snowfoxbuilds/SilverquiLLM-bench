"""Tests for cards/foundations/artifacts_batch2.py — Batch 2 artifact cards.

Verifies:
- Each artifact has correct metadata (name, mana_cost, card_types, subtypes).
- Mana rocks produce mana via get_mana_abilities().
- Utility artifacts have correct activated abilities and state tracking.
- Artifact creatures have correct power/toughness, subtypes, keywords.
- Equipment cards have Equipment subtype.
- Vehicle has correct crew cost and stats.
- register_artifacts_batch2() registers all 27 cards.
"""

from __future__ import annotations

import pytest

from cards.foundations.artifacts_batch2 import (
    AdaptiveAutomaton,
    BannerOfKinship,
    CampusGuide,
    CarnelianOrbOfDragonkind,
    CrystalBarricade,
    CultivatorsCaravan,
    DarksteelColossus,
    DiamondMare,
    ExpeditionMap,
    FeldonsCane,
    FishingPole,
    GateColossus,
    GildedLotus,
    GoblinFirebomb,
    HeraldicBanner,
    Juggernaut,
    MazemindTome,
    PiratesCutlass,
    PyromancersGoggles,
    RamosDragonEngine,
    RavenousAmulet,
    ScrawlingCrawler,
    SorcerousSpyglass,
    SoulGuideLantern,
    SteelHellkite,
    ThreeTreeMascot,
    WishclawTalisman,
    register_artifacts_batch2,
)
from cards.registry import CardRegistry
from engine.card import Creature, GameObject
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone


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


def _activate_mana_ability(artifact, game):
    """Activate the first mana ability on an artifact. Returns True if paid cost."""
    abilities = artifact.get_mana_abilities()
    assert len(abilities) > 0, f"{artifact.name} has no mana abilities"
    ability = abilities[0]
    if ability.cost(game, artifact):
        ability.mana_produced(game)
        return True
    return False


# ---------------------------------------------------------------------------
# Mana Rocks — Metadata
# ---------------------------------------------------------------------------

class TestGildedLotus:
    def test_metadata(self):
        card = GildedLotus()
        assert card.name == "Gilded Lotus"
        assert card.mana_cost == ManaCost.parse("{5}")
        assert CardType.ARTIFACT in card.card_types

    def test_mana_ability_produces_three_mana(self):
        game, p1, _ = _make_game()
        card = GildedLotus()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        initial = p1.mana_pool.get(ManaType.COLORLESS)
        result = _activate_mana_ability(card, game)
        assert result is True
        assert p1.mana_pool.get(ManaType.COLORLESS) - initial == 3

    def test_mana_ability_taps_artifact(self):
        game, p1, _ = _make_game()
        card = GildedLotus()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        _activate_mana_ability(card, game)
        assert card.is_tapped is True

    def test_cannot_activate_when_tapped(self):
        game, p1, _ = _make_game()
        card = GildedLotus()
        card.controller = p1
        card.owner = p1
        card.is_tapped = True
        game.get_battlefield(p1).add(card)
        result = _activate_mana_ability(card, game)
        assert result is False


class TestCarnelianOrbOfDragonkind:
    def test_metadata(self):
        card = CarnelianOrbOfDragonkind()
        assert card.name == "Carnelian Orb of Dragonkind"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert CardType.ARTIFACT in card.card_types

    def test_produces_red_mana(self):
        game, p1, _ = _make_game()
        card = CarnelianOrbOfDragonkind()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        initial = p1.mana_pool.get(ManaType.RED)
        _activate_mana_ability(card, game)
        assert p1.mana_pool.get(ManaType.RED) - initial == 1


class TestHeraldicBanner:
    def test_metadata(self):
        card = HeraldicBanner()
        assert card.name == "Heraldic Banner"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert CardType.ARTIFACT in card.card_types

    def test_has_chosen_color_attribute(self):
        card = HeraldicBanner()
        assert hasattr(card, "chosen_color")
        assert card.chosen_color is None

    def test_mana_ability_exists(self):
        card = HeraldicBanner()
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1


class TestPyromancersGoggles:
    def test_metadata(self):
        card = PyromancersGoggles()
        assert card.name == "Pyromancer's Goggles"
        assert card.mana_cost == ManaCost.parse("{5}")
        assert CardType.ARTIFACT in card.card_types
        assert Supertype.LEGENDARY in card.supertypes

    def test_produces_red_mana(self):
        game, p1, _ = _make_game()
        card = PyromancersGoggles()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        initial = p1.mana_pool.get(ManaType.RED)
        _activate_mana_ability(card, game)
        assert p1.mana_pool.get(ManaType.RED) - initial == 1


# ---------------------------------------------------------------------------
# Utility Artifacts — Metadata & Abilities
# ---------------------------------------------------------------------------

class TestBannerOfKinship:
    def test_metadata(self):
        card = BannerOfKinship()
        assert card.name == "Banner of Kinship"
        assert card.mana_cost == ManaCost.parse("{5}")
        assert CardType.ARTIFACT in card.card_types

    def test_has_chosen_type_and_counters(self):
        card = BannerOfKinship()
        assert hasattr(card, "chosen_type")
        assert hasattr(card, "fellowship_counters")
        assert card.fellowship_counters == 0


class TestRavenousAmulet:
    def test_metadata(self):
        card = RavenousAmulet()
        assert card.name == "Ravenous Amulet"
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_has_two_activated_abilities(self):
        card = RavenousAmulet()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

    def test_soul_counters_start_at_zero(self):
        card = RavenousAmulet()
        assert card.soul_counters == 0

    def test_draw_ability_increments_soul_counter(self):
        game, p1, _ = _make_game()
        card = RavenousAmulet()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        # Add cards to library for draw
        from engine.card import CardImpl
        dummy = CardImpl(name="Dummy")
        dummy.owner = p1
        p1.zones[Zone.LIBRARY].add(dummy)

        abilities = card.get_activated_abilities()
        draw_ability = abilities[0]
        draw_ability.cost(game, card)
        draw_ability.effect(game)
        assert card.soul_counters == 1

    def test_drain_ability_reduces_opponent_life(self):
        game, p1, p2 = _make_game()
        card = RavenousAmulet()
        card.controller = p1
        card.owner = p1
        card.soul_counters = 3
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        drain_ability = abilities[1]
        drain_ability.cost(game, card)
        drain_ability.effect(game)
        assert p2.life == 20 - 3


class TestGoblinFirebomb:
    def test_metadata(self):
        card = GoblinFirebomb()
        assert card.name == "Goblin Firebomb"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert Keyword.FLASH in card.keywords

    def test_has_activated_ability(self):
        card = GoblinFirebomb()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1


class TestFeldonsCane:
    def test_metadata(self):
        card = FeldonsCane()
        assert card.name == "Feldon's Cane"
        assert card.mana_cost == ManaCost.parse("{1}")

    def test_has_activated_ability(self):
        card = FeldonsCane()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1


class TestSoulGuideLantern:
    def test_metadata(self):
        card = SoulGuideLantern()
        assert card.name == "Soul-Guide Lantern"
        assert card.mana_cost == ManaCost.parse("{1}")

    def test_has_two_activated_abilities(self):
        card = SoulGuideLantern()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

    def test_exile_opponents_graveyard(self):
        game, p1, p2 = _make_game()
        card = SoulGuideLantern()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        # Add card to opponent's graveyard
        from engine.card import CardImpl
        dummy = CardImpl(name="GraveyardCard")
        dummy.owner = p2
        p2.zones[Zone.GRAVEYARD].add(dummy)
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 1

        abilities = card.get_activated_abilities()
        exile_ability = abilities[0]
        exile_ability.cost(game, card)
        exile_ability.effect(game)
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0


class TestSorcerousSpyglass:
    def test_metadata(self):
        card = SorcerousSpyglass()
        assert card.name == "Sorcerous Spyglass"
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_has_chosen_name_attribute(self):
        card = SorcerousSpyglass()
        assert hasattr(card, "chosen_name")
        assert card.chosen_name is None


class TestMazemindTome:
    def test_metadata(self):
        card = MazemindTome()
        assert card.name == "Mazemind Tome"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert "Book" in card.subtypes

    def test_page_counters_start_at_zero(self):
        card = MazemindTome()
        assert card.page_counters == 0

    def test_has_two_activated_abilities(self):
        card = MazemindTome()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

    def test_scry_increments_page_counter(self):
        game, p1, _ = _make_game()
        card = MazemindTome()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        scry_ability = abilities[0]
        scry_ability.cost(game, card)
        scry_ability.effect(game)
        assert card.page_counters == 1

    def test_exile_and_gain_life_at_four_counters(self):
        game, p1, _ = _make_game()
        card = MazemindTome()
        card.controller = p1
        card.owner = p1
        card.page_counters = 3  # next increment reaches 4
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        scry_ability = abilities[0]
        scry_ability.cost(game, card)
        scry_ability.effect(game)
        assert card.page_counters == 4
        assert p1.life == 20 + 4


class TestExpeditionMap:
    def test_metadata(self):
        card = ExpeditionMap()
        assert card.name == "Expedition Map"
        assert card.mana_cost == ManaCost.parse("{1}")

    def test_has_activated_ability(self):
        card = ExpeditionMap()
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1


class TestWishclawTalisman:
    def test_metadata(self):
        card = WishclawTalisman()
        assert card.name == "Wishclaw Talisman"
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_starts_with_three_wish_counters(self):
        card = WishclawTalisman()
        assert card.wish_counters == 3

    def test_activation_removes_wish_counter(self):
        game, p1, _ = _make_game()
        card = WishclawTalisman()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        result = ability.cost(game, card)
        assert result is True
        assert card.wish_counters == 2

    def test_cannot_activate_with_zero_counters(self):
        game, p1, _ = _make_game()
        card = WishclawTalisman()
        card.controller = p1
        card.wish_counters = 0
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        result = ability.cost(game, card)
        assert result is False


# ---------------------------------------------------------------------------
# Equipment (batch 2)
# ---------------------------------------------------------------------------

class TestFishingPole:
    def test_metadata(self):
        card = FishingPole()
        assert card.name == "Fishing Pole"
        assert card.mana_cost == ManaCost.parse("{1}")
        assert "Equipment" in card.subtypes

    def test_bait_counters_start_at_zero(self):
        card = FishingPole()
        assert card.bait_counters == 0


class TestPiratesCutlass:
    def test_metadata(self):
        card = PiratesCutlass()
        assert card.name == "Pirate's Cutlass"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert "Equipment" in card.subtypes


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

class TestCultivatorsCaravan:
    def test_metadata(self):
        card = CultivatorsCaravan()
        assert card.name == "Cultivator's Caravan"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert "Vehicle" in card.subtypes

    def test_power_toughness(self):
        card = CultivatorsCaravan()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_crew_cost(self):
        card = CultivatorsCaravan()
        assert card.crew_cost == 3

    def test_mana_ability(self):
        game, p1, _ = _make_game()
        card = CultivatorsCaravan()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        result = _activate_mana_ability(card, game)
        assert result is True


# ---------------------------------------------------------------------------
# Artifact Creatures — Metadata & Stats
# ---------------------------------------------------------------------------

class TestCrystalBarricade:
    def test_metadata(self):
        card = CrystalBarricade()
        assert card.name == "Crystal Barricade"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = CrystalBarricade()
        assert card.base_power == 0
        assert card.base_toughness == 4

    def test_subtypes(self):
        card = CrystalBarricade()
        assert "Wall" in card.subtypes

    def test_has_defender(self):
        card = CrystalBarricade()
        assert Keyword.DEFENDER in card.keywords


class TestScrawlingCrawler:
    def test_metadata(self):
        card = ScrawlingCrawler()
        assert card.name == "Scrawling Crawler"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = ScrawlingCrawler()
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self):
        card = ScrawlingCrawler()
        assert "Phyrexian" in card.subtypes
        assert "Construct" in card.subtypes


class TestCampusGuide:
    def test_metadata(self):
        card = CampusGuide()
        assert card.name == "Campus Guide"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = CampusGuide()
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_subtypes(self):
        card = CampusGuide()
        assert "Golem" in card.subtypes


class TestJuggernaut:
    def test_metadata(self):
        card = Juggernaut()
        assert card.name == "Juggernaut"
        assert card.mana_cost == ManaCost.parse("{4}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = Juggernaut()
        assert card.base_power == 5
        assert card.base_toughness == 3

    def test_must_attack(self):
        card = Juggernaut()
        assert card.must_attack is True

    def test_cant_be_blocked_by_walls(self):
        card = Juggernaut()
        assert card.cant_be_blocked_by_walls is True


class TestDarksteelColossus:
    def test_metadata(self):
        card = DarksteelColossus()
        assert card.name == "Darksteel Colossus"
        assert card.mana_cost == ManaCost.parse("{11}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = DarksteelColossus()
        assert card.base_power == 11
        assert card.base_toughness == 11

    def test_keywords(self):
        card = DarksteelColossus()
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.INDESTRUCTIBLE in card.keywords

    def test_subtypes(self):
        card = DarksteelColossus()
        assert "Golem" in card.subtypes


class TestDiamondMare:
    def test_metadata(self):
        card = DiamondMare()
        assert card.name == "Diamond Mare"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = DiamondMare()
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_subtypes(self):
        card = DiamondMare()
        assert "Horse" in card.subtypes

    def test_chosen_color_starts_none(self):
        card = DiamondMare()
        assert card.chosen_color is None


class TestGateColossus:
    def test_metadata(self):
        card = GateColossus()
        assert card.name == "Gate Colossus"
        assert card.mana_cost == ManaCost.parse("{8}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = GateColossus()
        assert card.base_power == 8
        assert card.base_toughness == 8

    def test_subtypes(self):
        card = GateColossus()
        assert "Construct" in card.subtypes


class TestSteelHellkite:
    def test_metadata(self):
        card = SteelHellkite()
        assert card.name == "Steel Hellkite"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = SteelHellkite()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self):
        card = SteelHellkite()
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self):
        card = SteelHellkite()
        assert "Dragon" in card.subtypes

    def test_pump_ability_increases_power(self):
        game, p1, _ = _make_game()
        card = SteelHellkite()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        initial_power = card.base_power
        abilities = card.get_activated_abilities()
        pump = abilities[0]
        pump.cost(game, card)
        pump.effect(game)
        assert card.base_power == initial_power + 1


class TestThreeTreeMascot:
    def test_metadata(self):
        card = ThreeTreeMascot()
        assert card.name == "Three Tree Mascot"
        assert card.mana_cost == ManaCost.parse("{2}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = ThreeTreeMascot()
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_changeling(self):
        card = ThreeTreeMascot()
        assert card.is_changeling is True

    def test_subtypes(self):
        card = ThreeTreeMascot()
        assert "Shapeshifter" in card.subtypes

    def test_mana_ability(self):
        game, p1, _ = _make_game()
        card = ThreeTreeMascot()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)
        result = _activate_mana_ability(card, game)
        assert result is True


class TestAdaptiveAutomaton:
    def test_metadata(self):
        card = AdaptiveAutomaton()
        assert card.name == "Adaptive Automaton"
        assert card.mana_cost == ManaCost.parse("{3}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_stats(self):
        card = AdaptiveAutomaton()
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self):
        card = AdaptiveAutomaton()
        assert "Construct" in card.subtypes

    def test_chosen_type_starts_none(self):
        card = AdaptiveAutomaton()
        assert card.chosen_type is None


class TestRamosDragonEngine:
    def test_metadata(self):
        card = RamosDragonEngine()
        assert card.name == "Ramos, Dragon Engine"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes

    def test_stats(self):
        card = RamosDragonEngine()
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying(self):
        card = RamosDragonEngine()
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self):
        card = RamosDragonEngine()
        assert "Dragon" in card.subtypes

    def test_activated_ability_requires_five_counters(self):
        game, p1, _ = _make_game()
        card = RamosDragonEngine()
        card.controller = p1
        card.owner = p1
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        ability = abilities[0]

        # Should fail with no counters
        card.plus_one_counters = 3
        result = ability.cost(game, card)
        assert result is False

    def test_activated_ability_adds_wubrg_mana(self):
        game, p1, _ = _make_game()
        card = RamosDragonEngine()
        card.controller = p1
        card.owner = p1
        card.plus_one_counters = 5
        game.get_battlefield(p1).add(card)

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        result = ability.cost(game, card)
        assert result is True
        assert card.plus_one_counters == 0
        ability.effect(game)
        assert p1.mana_pool.get(ManaType.WHITE) >= 2
        assert p1.mana_pool.get(ManaType.BLUE) >= 2
        assert p1.mana_pool.get(ManaType.BLACK) >= 2
        assert p1.mana_pool.get(ManaType.RED) >= 2
        assert p1.mana_pool.get(ManaType.GREEN) >= 2


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_all_27_artifacts(self):
        registry = CardRegistry()
        register_artifacts_batch2(registry)
        expected_names = [
            "Gilded Lotus",
            "Carnelian Orb of Dragonkind",
            "Heraldic Banner",
            "Pyromancer's Goggles",
            "Banner of Kinship",
            "Ravenous Amulet",
            "Goblin Firebomb",
            "Feldon's Cane",
            "Soul-Guide Lantern",
            "Sorcerous Spyglass",
            "Mazemind Tome",
            "Expedition Map",
            "Wishclaw Talisman",
            "Fishing Pole",
            "Pirate's Cutlass",
            "Cultivator's Caravan",
            "Crystal Barricade",
            "Scrawling Crawler",
            "Campus Guide",
            "Juggernaut",
            "Darksteel Colossus",
            "Diamond Mare",
            "Gate Colossus",
            "Steel Hellkite",
            "Three Tree Mascot",
            "Adaptive Automaton",
            "Ramos, Dragon Engine",
        ]
        for name in expected_names:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_registered_count(self):
        registry = CardRegistry()
        register_artifacts_batch2(registry)
        # At least 27 cards registered
        count = 0
        for name in [
            "Gilded Lotus", "Carnelian Orb of Dragonkind", "Heraldic Banner",
            "Pyromancer's Goggles", "Banner of Kinship", "Ravenous Amulet",
            "Goblin Firebomb", "Feldon's Cane", "Soul-Guide Lantern",
            "Sorcerous Spyglass", "Mazemind Tome", "Expedition Map",
            "Wishclaw Talisman", "Fishing Pole", "Pirate's Cutlass",
            "Cultivator's Caravan", "Crystal Barricade", "Scrawling Crawler",
            "Campus Guide", "Juggernaut", "Darksteel Colossus",
            "Diamond Mare", "Gate Colossus", "Steel Hellkite",
            "Three Tree Mascot", "Adaptive Automaton", "Ramos, Dragon Engine",
        ]:
            if registry.get(name) is not None:
                count += 1
        assert count == 27
