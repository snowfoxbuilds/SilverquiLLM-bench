"""Tests for cards/fdn/_legacy/lands.py — Non-basic FDN land implementations.

Verifies:
- Each gain land subclasses Land and GainLand (and TapLand).
- Gain lands enter the battlefield tapped (register_triggers sets is_tapped).
- Gain lands grant 1 life on ETB (register_triggers increments controller.life).
- Each gain land has two mana abilities producing the correct colors.
- Tapping an already-tapped gain land fails (cost returns False).
- Utility lands (Rogue's Passage, Soulstone Sanctuary) produce {C}.
- Evolving Wilds has no mana abilities.
- register_lands registers all 13 cards in a CardRegistry.
- Registry metadata (name, collector number, type line).
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.lands import (
    BloodfellCaves,
    BlossomingSands,
    DismalBackwater,
    EvolvingWilds,
    GainLand,
    JungleHollow,
    RoguesPassage,
    RuggedHighlands,
    ScouredBarrens,
    SoulstoneSanctuary,
    SwiftwaterCliffs,
    TapLand,
    ThornwoodFalls,
    TranquilCove,
    WindScarredCrag,
    register_lands,
)
from cards.registry import CardRegistry
from engine.card import Land, ManaAbility
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, ManaType, Phase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game() -> GameState:
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return game


def _activate_mana_ability(land, game, index: int = 0) -> bool:
    """Activate the mana ability at *index* on *land*.

    Returns True if the cost was paid and mana produced, False if cost failed.
    """
    abilities = land.get_mana_abilities()
    assert len(abilities) > index, f"Expected at least {index + 1} mana abilities"
    ability = abilities[index]
    cost_paid = ability.cost(game, land)
    if not cost_paid:
        return False
    ability.mana_produced(game)
    return True


# ---------------------------------------------------------------------------
# Gain land data for parametrized tests
# ---------------------------------------------------------------------------

GAIN_LAND_DATA = [
    (BloodfellCaves, "Bloodfell Caves", "259", ManaType.BLACK, ManaType.RED),
    (BlossomingSands, "Blossoming Sands", "260", ManaType.GREEN, ManaType.WHITE),
    (DismalBackwater, "Dismal Backwater", "261", ManaType.BLUE, ManaType.BLACK),
    (JungleHollow, "Jungle Hollow", "263", ManaType.BLACK, ManaType.GREEN),
    (RuggedHighlands, "Rugged Highlands", "265", ManaType.RED, ManaType.GREEN),
    (ScouredBarrens, "Scoured Barrens", "266", ManaType.WHITE, ManaType.BLACK),
    (SwiftwaterCliffs, "Swiftwater Cliffs", "268", ManaType.BLUE, ManaType.RED),
    (ThornwoodFalls, "Thornwood Falls", "269", ManaType.GREEN, ManaType.BLUE),
    (TranquilCove, "Tranquil Cove", "270", ManaType.WHITE, ManaType.BLUE),
    (WindScarredCrag, "Wind-Scarred Crag", "271", ManaType.RED, ManaType.WHITE),
]


# ---------------------------------------------------------------------------
# Subclass / type checks
# ---------------------------------------------------------------------------

class TestGainLandSubclasses:
    """Each gain land is a Land, TapLand, and GainLand."""

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_is_land(self, cls, name, _cn, _m1, _m2) -> None:
        land = cls(name=name)
        assert isinstance(land, Land)
        assert isinstance(land, TapLand)
        assert isinstance(land, GainLand)

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_has_land_card_type(self, cls, name, _cn, _m1, _m2) -> None:
        land = cls(name=name)
        assert CardType.LAND in land.card_types


class TestUtilityLandSubclasses:
    """Utility lands are Land instances."""

    def test_rogues_passage_is_land(self) -> None:
        land = RoguesPassage(name="Rogue's Passage")
        assert isinstance(land, Land)
        assert CardType.LAND in land.card_types

    def test_soulstone_sanctuary_is_land(self) -> None:
        land = SoulstoneSanctuary(name="Soulstone Sanctuary")
        assert isinstance(land, Land)
        assert CardType.LAND in land.card_types

    def test_evolving_wilds_is_land(self) -> None:
        land = EvolvingWilds(name="Evolving Wilds")
        assert isinstance(land, Land)
        assert CardType.LAND in land.card_types


# ---------------------------------------------------------------------------
# ETB tapped behavior
# ---------------------------------------------------------------------------

class TestETBTapped:
    """Gain lands (and TapLand subclasses) enter tapped via register_triggers."""

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_gain_land_enters_tapped(self, cls, name, _cn, _m1, _m2) -> None:
        game = _make_game()
        player = game.players[0]
        land = cls(name=name, owner=player, controller=player)
        # Simulate ETB by calling register_triggers
        land.register_triggers(game)
        assert land.is_tapped is True

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_enters_tapped_flag_is_set(self, cls, name, _cn, _m1, _m2) -> None:
        land = cls(name=name)
        assert land.enters_tapped is True

    def test_rogues_passage_enters_untapped(self) -> None:
        """Utility lands should NOT enter tapped."""
        land = RoguesPassage(name="Rogue's Passage")
        assert not getattr(land, "enters_tapped", False)

    def test_soulstone_sanctuary_enters_untapped(self) -> None:
        land = SoulstoneSanctuary(name="Soulstone Sanctuary")
        assert not getattr(land, "enters_tapped", False)

    def test_evolving_wilds_enters_untapped(self) -> None:
        land = EvolvingWilds(name="Evolving Wilds")
        assert not getattr(land, "enters_tapped", False)


# ---------------------------------------------------------------------------
# Gain 1 life on ETB
# ---------------------------------------------------------------------------

class TestETBLifeGain:
    """Gain lands grant 1 life to the controller on ETB."""

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_gain_land_grants_one_life(self, cls, name, _cn, _m1, _m2) -> None:
        game = _make_game()
        player = game.players[0]
        initial_life = player.life
        land = cls(name=name, owner=player, controller=player)
        land.register_triggers(game)
        assert player.life == initial_life + 1

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_life_gain_only_affects_controller(self, cls, name, _cn, _m1, _m2) -> None:
        """Life gain should only affect the controller, not the opponent."""
        game = _make_game()
        controller = game.players[0]
        opponent = game.players[1]
        opponent_life_before = opponent.life
        land = cls(name=name, owner=controller, controller=controller)
        land.register_triggers(game)
        assert opponent.life == opponent_life_before


# ---------------------------------------------------------------------------
# Mana production — gain lands
# ---------------------------------------------------------------------------

class TestGainLandManaProduction:
    """Each gain land has two mana abilities producing its two colors."""

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_has_two_mana_abilities(self, cls, name, _cn, mana1, mana2) -> None:
        land = cls(name=name)
        abilities = land.get_mana_abilities()
        assert len(abilities) == 2

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_abilities_are_mana_ability_type(self, cls, name, _cn, mana1, mana2) -> None:
        land = cls(name=name)
        for ability in land.get_mana_abilities():
            assert isinstance(ability, ManaAbility)

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_first_ability_produces_correct_color(self, cls, name, _cn, mana1, mana2) -> None:
        game = _make_game()
        player = game.players[0]
        land = cls(name=name, owner=player, controller=player)
        # Must be untapped to activate
        land.is_tapped = False
        assert _activate_mana_ability(land, game, index=0) is True
        assert player.mana_pool.get(mana1) == 1

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_second_ability_produces_correct_color(self, cls, name, _cn, mana1, mana2) -> None:
        game = _make_game()
        player = game.players[0]
        land = cls(name=name, owner=player, controller=player)
        land.is_tapped = False
        assert _activate_mana_ability(land, game, index=1) is True
        assert player.mana_pool.get(mana2) == 1

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_tap_already_tapped_gain_land_fails(self, cls, name, _cn, mana1, mana2) -> None:
        game = _make_game()
        player = game.players[0]
        land = cls(name=name, owner=player, controller=player)
        land.is_tapped = True  # Simulate already tapped (e.g. from ETB)
        assert _activate_mana_ability(land, game, index=0) is False

    @pytest.mark.parametrize("cls,name,_cn,mana1,mana2", GAIN_LAND_DATA)
    def test_mana_produces_exactly_one(self, cls, name, _cn, mana1, mana2) -> None:
        """Each activation should add exactly 1 mana, total 1."""
        game = _make_game()
        player = game.players[0]
        land = cls(name=name, owner=player, controller=player)
        land.is_tapped = False
        _activate_mana_ability(land, game, index=0)
        assert player.mana_pool.total() == 1


# ---------------------------------------------------------------------------
# Mana production — utility lands
# ---------------------------------------------------------------------------

class TestUtilityLandMana:
    """Utility lands with mana abilities produce colorless mana."""

    def test_rogues_passage_produces_colorless(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = RoguesPassage(name="Rogue's Passage", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.COLORLESS) == 1

    def test_rogues_passage_has_one_mana_ability(self) -> None:
        land = RoguesPassage(name="Rogue's Passage")
        abilities = land.get_mana_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)

    def test_soulstone_sanctuary_produces_colorless(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.COLORLESS) == 1

    def test_soulstone_sanctuary_has_one_mana_ability(self) -> None:
        land = SoulstoneSanctuary(name="Soulstone Sanctuary")
        abilities = land.get_mana_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)

    def test_evolving_wilds_has_no_mana_abilities(self) -> None:
        """Evolving Wilds' sacrifice ability is not a mana ability."""
        land = EvolvingWilds(name="Evolving Wilds")
        abilities = land.get_mana_abilities()
        assert len(abilities) == 0

    def test_rogues_passage_tap_when_already_tapped_fails(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = RoguesPassage(name="Rogue's Passage", owner=player, controller=player)
        _activate_mana_ability(land, game)
        assert land.is_tapped is True
        assert _activate_mana_ability(land, game) is False


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegisterLands:
    """register_lands registers all 13 non-basic lands in a CardRegistry."""

    def test_registers_all_thirteen(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        assert len(registry) == 13

    def test_all_gain_land_names_registered(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        expected_names = {
            "Bloodfell Caves", "Blossoming Sands", "Dismal Backwater",
            "Jungle Hollow", "Rugged Highlands", "Scoured Barrens",
            "Swiftwater Cliffs", "Thornwood Falls", "Tranquil Cove",
            "Wind-Scarred Crag",
        }
        registered = set(registry.list_all())
        assert expected_names.issubset(registered)

    def test_utility_land_names_registered(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        for name in ("Rogue's Passage", "Soulstone Sanctuary", "Evolving Wilds"):
            assert name in registry

    @pytest.mark.parametrize("name,collector_number", [
        ("Bloodfell Caves", "259"),
        ("Blossoming Sands", "260"),
        ("Dismal Backwater", "261"),
        ("Jungle Hollow", "263"),
        ("Rugged Highlands", "265"),
        ("Scoured Barrens", "266"),
        ("Swiftwater Cliffs", "268"),
        ("Thornwood Falls", "269"),
        ("Tranquil Cove", "270"),
        ("Wind-Scarred Crag", "271"),
        ("Rogue's Passage", "264"),
        ("Soulstone Sanctuary", "133"),
        ("Evolving Wilds", "262"),
    ])
    def test_collector_number(self, name, collector_number) -> None:
        registry = CardRegistry()
        register_lands(registry)
        _cls, meta = registry.get(name)
        assert meta.collector_number == collector_number

    def test_metadata_type_line_is_land(self) -> None:
        """All non-basic lands have type_line containing 'Land'."""
        registry = CardRegistry()
        register_lands(registry)
        for name in registry.list_all():
            _cls, meta = registry.get(name)
            assert "Land" in meta.type_line

    def test_metadata_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        registry = CardRegistry()
        register_lands(registry)
        for name in registry.list_all():
            _cls, meta = registry.get(name)
            assert meta.mana_cost_str == ""

    def test_metadata_set_code(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        for name in registry.list_all():
            _cls, meta = registry.get(name)
            assert meta.set_code == "fdn"


# ---------------------------------------------------------------------------
# Registry create_instance
# ---------------------------------------------------------------------------

class TestRegistryCreateInstance:
    """Verify create_instance produces the correct land types."""

    @pytest.mark.parametrize("cls,name,_cn,_m1,_m2", GAIN_LAND_DATA)
    def test_gain_land_instance_type(self, cls, name, _cn, _m1, _m2) -> None:
        registry = CardRegistry()
        register_lands(registry)
        player = DeterministicPlayer("Owner", [])
        instance = registry.create_instance(name, owner=player)
        assert isinstance(instance, cls)
        assert isinstance(instance, GainLand)
        assert isinstance(instance, Land)

    def test_rogues_passage_instance(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        player = DeterministicPlayer("Owner", [])
        instance = registry.create_instance("Rogue's Passage", owner=player)
        assert isinstance(instance, RoguesPassage)

    def test_evolving_wilds_instance(self) -> None:
        registry = CardRegistry()
        register_lands(registry)
        player = DeterministicPlayer("Owner", [])
        instance = registry.create_instance("Evolving Wilds", owner=player)
        assert isinstance(instance, EvolvingWilds)
