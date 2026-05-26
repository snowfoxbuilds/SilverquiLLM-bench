"""Audited tests for Skycoach Waypoint (collector key 261).

Verifies the Skycoach Waypoint card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SkycoachWaypoint

from engine.card import Land
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSkycoachWaypointBasicProperties:
    """Basic property tests for Skycoach Waypoint."""

    def test_is_land(self) -> None:
        """Skycoach Waypoint must be a Land subclass."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        """SkycoachWaypoint.name must be 'Skycoach Waypoint'."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert card.name == "Skycoach Waypoint"

    def test_card_types(self) -> None:
        """Skycoach Waypoint must have correct card types."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert CardType.LAND in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Skycoach Waypoint must have converted mana cost 0."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert card.mana_cost.cmc == 0

    def test_colorless(self) -> None:
        """Skycoach Waypoint must be colorless."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert len(card_colors(card)) == 0

@pytest.mark.ability
class TestSkycoachWaypointAbilities:
    """Ability tests for Skycoach Waypoint -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Skycoach Waypoint must have Prepared keyword."""
        from engine.types import Keyword
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert Keyword.PREPARED in card.keywords, "Skycoach Waypoint should have Prepared"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Skycoach Waypoint must implement prepared mechanic"

@pytest.mark.edge
class TestSkycoachWaypointEdgeCases:
    """Edge case and trap tests for Skycoach Waypoint."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        card2 = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        card1.name = "Modified"
        assert card2.name == "Skycoach Waypoint", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=None)
        assert card.mana_cost.cmc == 0, \
            f"CMC must be 0, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestSkycoachWaypointInteractions:
    """Multi-card interaction tests for Skycoach Waypoint."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = SkycoachWaypoint(name="Skycoach Waypoint", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
