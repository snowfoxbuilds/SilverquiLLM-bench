"""Tests for SOS 261 — Skycoach Waypoint.

Land:
- {T}: Add {C}.
- {3}, {T}: Target creature becomes prepared.
"""

from __future__ import annotations

from cards.sos.sos_261.card_impl import SkycoachWaypoint
from engine.card import Creature, Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSkycoachWaypointProperties:
    """Static card data should match the SOS 261 spec."""

    def test_is_land(self) -> None:
        card = SkycoachWaypoint(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = SkycoachWaypoint(owner=None)
        assert card.name == "Skycoach Waypoint"

    def test_has_land_card_type(self) -> None:
        card = SkycoachWaypoint(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = SkycoachWaypoint(owner=None)
        assert card.mana_cost is None or str(card.mana_cost) == ""


class TestSkycoachWaypointManaAbility:
    """{T}: Add {C}."""

    def test_has_mana_abilities(self) -> None:
        card = SkycoachWaypoint(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_colorless(self) -> None:
        card = SkycoachWaypoint(owner=None)
        abilities = card.get_mana_abilities()
        colorless_found = any(
            ManaType.COLORLESS in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert colorless_found is True


class TestSkycoachWaypointPrepareAbility:
    """{3}, {T}: Target creature becomes prepared."""

    def test_has_activated_abilities(self) -> None:
        card = SkycoachWaypoint(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_prepare_ability_makes_creature_prepared(self) -> None:
        """Activating the ability should mark the target creature as prepared."""
        game = create_game()
        p1 = game.players[0]
        card = SkycoachWaypoint(owner=p1, controller=p1)
        target = Creature(name="Test Creature", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, target])
        card.is_tapped = False
        abilities = card.get_activated_abilities()
        prepare_ability = abilities[0]
        prepare_ability.activate(game, card, p1, targets=[target])
        assert getattr(target, 'is_prepared', False) is True

    def test_prepare_ability_taps_land(self) -> None:
        """Activating costs {T}, so land should be tapped after."""
        game = create_game()
        p1 = game.players[0]
        card = SkycoachWaypoint(owner=p1, controller=p1)
        target = Creature(name="Test Creature", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, target],
                        mana={ManaType.COLORLESS: 3})
        card.is_tapped = False
        abilities = card.get_activated_abilities()
        prepare_ability = abilities[0]
        prepare_ability.activate(game, card, p1, targets=[target])
        assert card.is_tapped is True
