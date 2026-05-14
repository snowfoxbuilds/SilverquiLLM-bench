"""Tests for cards/fdn/_legacy/basic_lands.py — Basic land implementations.

Verifies:
- Each land (Plains, Island, Swamp, Mountain, Forest) subclasses Land.
- Each has Supertype.BASIC in supertypes.
- Each has the correct land subtype (e.g. "Plains" for Plains).
- Each has CardType.LAND in card_types.
- Each taps to produce exactly 1 mana of its color.
- Tapping an already-tapped land fails (cost returns False).
- Can't play a second land in the same turn (land_plays_remaining enforced).
- register_basic_lands registers all 5 in a CardRegistry.
- Registry create_instance produces the correct land subclass.
- Integration: play land from hand, tap for mana, verify mana pool.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.basic_lands import (
    Forest,
    Island,
    Mountain,
    Plains,
    Swamp,
    register_basic_lands,
)
from cards.registry import CardRegistry
from engine.card import Land, ManaAbility
from engine.casting import CastingError, play_land
from engine.game_state import GameState
from engine.mana import ManaPool
from engine.player import DeterministicPlayer
from engine.types import CardType, ManaType, Phase, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    return game


def _activate_mana_ability(land, game: GameState) -> bool:
    """Activate the first mana ability on *land*.

    Returns True if the cost was paid (i.e. the ability resolved),
    False if the tap cost failed.
    """
    abilities = land.get_mana_abilities()
    assert len(abilities) >= 1, "Land should have at least one mana ability"
    ability = abilities[0]
    # Pay cost
    cost_paid = ability.cost(game, land)
    if not cost_paid:
        return False
    # Produce mana
    ability.mana_produced(game)
    return True


# ---------------------------------------------------------------------------
# Subclass checks — each land is a Land
# ---------------------------------------------------------------------------

class TestLandSubclasses:
    """Verify each basic land subclasses Land and has CardType.LAND."""

    def test_plains_is_land(self) -> None:
        p = Plains(name="Plains")
        assert isinstance(p, Land)
        assert CardType.LAND in p.card_types

    def test_island_is_land(self) -> None:
        i = Island(name="Island")
        assert isinstance(i, Land)
        assert CardType.LAND in i.card_types

    def test_swamp_is_land(self) -> None:
        s = Swamp(name="Swamp")
        assert isinstance(s, Land)
        assert CardType.LAND in s.card_types

    def test_mountain_is_land(self) -> None:
        m = Mountain(name="Mountain")
        assert isinstance(m, Land)
        assert CardType.LAND in m.card_types

    def test_forest_is_land(self) -> None:
        f = Forest(name="Forest")
        assert isinstance(f, Land)
        assert CardType.LAND in f.card_types


# ---------------------------------------------------------------------------
# Supertype.BASIC
# ---------------------------------------------------------------------------

class TestBasicSupertype:
    """Verify each basic land has Supertype.BASIC in supertypes."""

    @pytest.mark.parametrize("cls,name", [
        (Plains, "Plains"),
        (Island, "Island"),
        (Swamp, "Swamp"),
        (Mountain, "Mountain"),
        (Forest, "Forest"),
    ])
    def test_has_basic_supertype(self, cls, name) -> None:
        land = cls(name=name)
        assert Supertype.BASIC in land.supertypes


# ---------------------------------------------------------------------------
# Subtypes
# ---------------------------------------------------------------------------

class TestLandSubtypes:
    """Verify each basic land has the correct land subtype."""

    @pytest.mark.parametrize("cls,expected_subtype", [
        (Plains, "Plains"),
        (Island, "Island"),
        (Swamp, "Swamp"),
        (Mountain, "Mountain"),
        (Forest, "Forest"),
    ])
    def test_has_correct_subtype(self, cls, expected_subtype) -> None:
        land = cls(name=expected_subtype)
        assert expected_subtype in land.subtypes


# ---------------------------------------------------------------------------
# Mana production
# ---------------------------------------------------------------------------

class TestManaProduction:
    """Verify each basic land taps to produce 1 mana of its color."""

    def test_plains_produces_white_mana(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Plains(name="Plains", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.WHITE) == 1

    def test_island_produces_blue_mana(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Island(name="Island", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.BLUE) == 1

    def test_swamp_produces_black_mana(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Swamp(name="Swamp", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.BLACK) == 1

    def test_mountain_produces_red_mana(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Mountain(name="Mountain", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.RED) == 1

    def test_forest_produces_green_mana(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Forest(name="Forest", owner=player, controller=player)
        assert _activate_mana_ability(land, game) is True
        assert player.mana_pool.get(ManaType.GREEN) == 1

    def test_mana_ability_produces_exactly_one(self) -> None:
        """Activating once should add exactly 1 mana, no more."""
        game = _make_game()
        player = game.players[0]
        land = Plains(name="Plains", owner=player, controller=player)
        _activate_mana_ability(land, game)
        assert player.mana_pool.get(ManaType.WHITE) == 1
        assert player.mana_pool.total() == 1

    def test_mana_ability_returns_mana_ability_type(self) -> None:
        """get_mana_abilities should return ManaAbility instances."""
        land = Plains(name="Plains")
        abilities = land.get_mana_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)


# ---------------------------------------------------------------------------
# Tapping already-tapped land
# ---------------------------------------------------------------------------

class TestTappedLand:
    """Verify that tapping an already-tapped land fails."""

    def test_tap_already_tapped_plains_fails(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Plains(name="Plains", owner=player, controller=player)

        # First tap succeeds
        assert _activate_mana_ability(land, game) is True
        assert land.is_tapped is True

        # Second tap fails
        assert _activate_mana_ability(land, game) is False
        # Mana pool should still have exactly 1 (no second mana added)
        assert player.mana_pool.get(ManaType.WHITE) == 1

    def test_tap_already_tapped_mountain_fails(self) -> None:
        game = _make_game()
        player = game.players[0]
        land = Mountain(name="Mountain", owner=player, controller=player)

        assert _activate_mana_ability(land, game) is True
        assert land.is_tapped is True
        assert _activate_mana_ability(land, game) is False
        assert player.mana_pool.get(ManaType.RED) == 1


# ---------------------------------------------------------------------------
# Can't play a second land same turn
# ---------------------------------------------------------------------------

class TestLandPlayLimit:
    """Verify that a player cannot play a second land in the same turn."""

    def test_second_land_play_raises(self) -> None:
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        land1 = Plains(name="Plains", owner=player, controller=player)
        land2 = Island(name="Island", owner=player, controller=player)

        # Add both lands to hand
        hand = game.get_hand(player)
        hand.add(land1)
        hand.add(land2)

        # First land play succeeds
        play_land(game, player, land1)

        # Second land play should fail
        with pytest.raises(CastingError, match="no land plays remaining"):
            play_land(game, player, land2)

    def test_first_land_play_decrements_counter(self) -> None:
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        land = Plains(name="Plains", owner=player, controller=player)
        hand = game.get_hand(player)
        hand.add(land)

        initial_plays = player.land_plays_remaining
        play_land(game, player, land)
        assert player.land_plays_remaining == initial_plays - 1


# ---------------------------------------------------------------------------
# register_basic_lands
# ---------------------------------------------------------------------------

class TestRegisterBasicLands:
    """Verify register_basic_lands registers all 5 lands in a registry."""

    def test_registers_all_five(self) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        assert len(registry) == 5

    def test_registered_names(self) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        expected = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
        assert set(registry.list_all()) == expected

    def test_each_name_in_registry(self) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        for name in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
            assert name in registry

    def test_registry_metadata_type_line(self) -> None:
        """Each registered land should have a 'Basic Land — <name>' type line."""
        registry = CardRegistry()
        register_basic_lands(registry)
        for name in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
            _cls, meta = registry.get(name)
            assert f"Basic Land" in meta.type_line
            assert name in meta.type_line

    def test_registry_metadata_no_mana_cost(self) -> None:
        """Basic lands have no mana cost."""
        registry = CardRegistry()
        register_basic_lands(registry)
        for name in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
            _cls, meta = registry.get(name)
            assert meta.mana_cost_str == ""


# ---------------------------------------------------------------------------
# Registry create_instance
# ---------------------------------------------------------------------------

class TestRegistryCreateInstance:
    """Verify that create_instance produces the correct land type."""

    @pytest.mark.parametrize("name,expected_class", [
        ("Plains", Plains),
        ("Island", Island),
        ("Swamp", Swamp),
        ("Mountain", Mountain),
        ("Forest", Forest),
    ])
    def test_create_instance_type(self, name, expected_class) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        player = _make_player()
        instance = registry.create_instance(name, owner=player)
        assert isinstance(instance, expected_class)
        assert isinstance(instance, Land)

    def test_create_instance_has_basic_supertype(self) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        player = _make_player()
        for name in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
            instance = registry.create_instance(name, owner=player)
            assert Supertype.BASIC in instance.supertypes

    def test_create_instance_has_owner(self) -> None:
        registry = CardRegistry()
        register_basic_lands(registry)
        player = _make_player("Owner")
        instance = registry.create_instance("Plains", owner=player)
        assert instance.owner is player


# ---------------------------------------------------------------------------
# Integration: play land from hand → tap → verify mana pool
# ---------------------------------------------------------------------------

class TestIntegrationPlayAndTap:
    """Integration test: play a land from hand, tap it, verify mana pool."""

    def test_play_plains_tap_for_white(self) -> None:
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        plains = Plains(name="Plains", owner=player, controller=player)
        game.get_hand(player).add(plains)

        # Play the land
        play_land(game, player, plains)

        # Verify it's on the battlefield
        bf = game.get_battlefield(player)
        assert bf.contains(plains)

        # Verify it's not in hand
        hand = game.get_hand(player)
        assert not hand.contains(plains)

        # Tap for mana
        assert _activate_mana_ability(plains, game) is True

        # Verify mana pool
        assert player.mana_pool.get(ManaType.WHITE) == 1

    def test_play_forest_tap_for_green(self) -> None:
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        forest = Forest(name="Forest", owner=player, controller=player)
        game.get_hand(player).add(forest)

        play_land(game, player, forest)

        bf = game.get_battlefield(player)
        assert bf.contains(forest)

        assert _activate_mana_ability(forest, game) is True
        assert player.mana_pool.get(ManaType.GREEN) == 1

    def test_play_land_then_tap_then_no_second_land(self) -> None:
        """Full cycle: play a land, tap it, then verify a second land can't be played."""
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        plains = Plains(name="Plains", owner=player, controller=player)
        island = Island(name="Island", owner=player, controller=player)
        game.get_hand(player).add(plains)
        game.get_hand(player).add(island)

        # Play first land
        play_land(game, player, plains)
        # Tap it
        _activate_mana_ability(plains, game)
        assert player.mana_pool.get(ManaType.WHITE) == 1

        # Second land should fail
        with pytest.raises(CastingError, match="no land plays remaining"):
            play_land(game, player, island)

    def test_land_starts_untapped(self) -> None:
        """A land that was just played should start untapped."""
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        player = game.players[0]
        game.active_player_index = 0

        plains = Plains(name="Plains", owner=player, controller=player)
        game.get_hand(player).add(plains)

        play_land(game, player, plains)
        assert plains.is_tapped is False

    def test_no_mana_from_controller_none(self) -> None:
        """If the land has no controller, tapping should not crash but no mana added."""
        game = _make_game()
        land = Plains(name="Plains", owner=None, controller=None)
        # The effect should not crash even with no controller
        abilities = land.get_mana_abilities()
        ability = abilities[0]
        # Tap cost should work
        cost_paid = ability.cost(game, land)
        assert cost_paid is True
        # mana_produced shouldn't crash (controller is None, no mana added)
        ability.mana_produced(game)
