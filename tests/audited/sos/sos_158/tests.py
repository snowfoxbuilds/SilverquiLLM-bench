"""Audited tests for Planar Engineering (collector number 158).

Verifies the Planar Engineering card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PlanarEngineering

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPlanarEngineeringBasicProperties:
    """Planar Engineering basic property tests."""

    def test_is_sorcery(self) -> None:
        """Planar Engineering must be a Sorcery subclass."""
        card = PlanarEngineering(name="Planar Engineering", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """PlanarEngineering.name must be 'Planar Engineering'."""
        card = PlanarEngineering(name="Planar Engineering", owner=None)
        assert card.name == "Planar Engineering"

    def test_card_type(self) -> None:
        """Planar Engineering must have CardType.SORCERY."""
        card = PlanarEngineering(name="Planar Engineering", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Planar Engineering must have converted mana cost 4."""
        card = PlanarEngineering(name="Planar Engineering", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Planar Engineering must have colors ['G']."""
        card = PlanarEngineering(name="Planar Engineering", owner=None)
        for c in ["G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestPlanarEngineeringAbilities:
    """Planar Engineering ability tests — expected to fail against stubs."""

    def test_requires_two_land_sacrifice(self) -> None:
        """Planar Engineering requires sacrificing two lands as part of its effect.

        Oracle: Sacrifice two lands. Search your library for four basic land cards, put them onto the battlefield tapped, then shuffle.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import Land

        game = create_game()
        player = game.players[0]
        # Put two lands on battlefield to sacrifice
        land1 = Land(name="Forest", owner=player)
        land2 = Land(name="Mountain", owner=player)
        set_board_state(game, 0, battlefield=[land1, land2])
        # Stock library with basic lands to search for
        for i in range(5):
            lib_land = Land(name="Plains", owner=player)
            lib_land.subtypes = {"Plains", "Basic"}
            player.zones[Zone.LIBRARY].add(lib_land)

        bf_before = len(game.get_battlefield(player).get_all())
        card = PlanarEngineering(name="Planar Engineering", owner=player)
        card.controller = player
        card.on_resolve(game)

        # The two original lands should be gone (sacrificed)
        bf_all = game.get_battlefield(player).get_all()
        assert land1 not in bf_all, "Expected first land to be sacrificed"
        assert land2 not in bf_all, "Expected second land to be sacrificed"

    def test_on_resolve_searches_four_basic_lands(self) -> None:
        """Planar Engineering should put four basic land cards onto the battlefield tapped.

        Oracle: Sacrifice two lands. Search your library for four basic land cards, put them onto the battlefield tapped, then shuffle.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import Land

        game = create_game()
        player = game.players[0]
        # Put two lands on battlefield to sacrifice
        land1 = Land(name="Forest", owner=player)
        land2 = Land(name="Mountain", owner=player)
        set_board_state(game, 0, battlefield=[land1, land2])
        # Stock library with 5 basic lands
        lib_lands = []
        for i in range(5):
            lib_land = Land(name=f"Plains{i}", owner=player)
            lib_land.subtypes = {"Plains", "Basic"}
            player.zones[Zone.LIBRARY].add(lib_land)
            lib_lands.append(lib_land)

        card = PlanarEngineering(name="Planar Engineering", owner=player)
        card.controller = player
        card.on_resolve(game)

        # After resolution, battlefield should have gained lands from library
        bf_all = game.get_battlefield(player).get_all()
        # At least some basic lands from library should be on battlefield
        bf_names = [getattr(c, "name", "") for c in bf_all]
        found_plains = sum(1 for n in bf_names if "Plains" in n)
        assert found_plains >= 1, (
            f"Expected basic lands on battlefield from library search, got: {bf_names}"
        )
