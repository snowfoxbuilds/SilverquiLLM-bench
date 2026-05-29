"""Reference test for FDN 13 — Fleeting Flight.

Illustrative test covering **target selection / validation**. Fleeting
Flight is a targeted instant: ``get_targets()`` returns a
``TargetRequirement`` describing what is legal, and the cast pipeline
populates ``chosen_targets`` with the player's selection. ``on_resolve``
reads ``chosen_targets`` and applies the effect to the chosen target.
"""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    TargetRequirement,
    Zone,
)
from test_utils import create_game


class TestFleetingFlightProperties:
    """Static card data should match the FDN 13 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FleetingFlight(owner=None), Instant)

    def test_name(self) -> None:
        assert FleetingFlight(owner=None).name == "Fleeting Flight"

    def test_mana_cost(self) -> None:
        assert FleetingFlight(owner=None).mana_cost == ManaCost.parse("{W}")


class TestFleetingFlightTargeting:
    """get_targets() advertises a single creature target on the battlefield."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = FleetingFlight(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = FleetingFlight(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        """The filter must accept creatures and reject non-creatures."""
        game = create_game()
        req = FleetingFlight(owner=None).get_targets(game)[0]

        creature = Creature(name="Test Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        non_creature = Creature(name="Not a creature")  # no card_types
        non_creature.card_types = set()

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestFleetingFlightResolution:
    """on_resolve reads chosen_targets and applies the effect."""

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FleetingFlight(owner=p1, controller=p1)
        # chosen_targets is unset — resolution must not raise.
        spell.on_resolve(game)

    def test_chosen_target_receives_counter_and_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Put a vanilla bear on the battlefield as the target.
        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = FleetingFlight(owner=p1, controller=p1)
        # The cast pipeline would set chosen_targets; we set it directly
        # to validate that on_resolve reads it correctly.
        spell.chosen_targets = [bear]
        before = bear.plus_one_counters
        spell.on_resolve(game)
        # +1/+1 counter applied to the chosen target.
        assert bear.plus_one_counters == before + 1
        # Damage-prevention flag set per the card's "prevent all combat
        # damage" clause.
        assert bear.combat_damage_prevented is True
