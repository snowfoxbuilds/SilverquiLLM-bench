"""Tests for SOS 6 — Ajani's Response.

Ajani's Response is a {4}{W} Instant that destroys target creature.
It costs {3} less if it targets a tapped creature.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_6.card_impl import AjanisResponse
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell
from engine.types import ManaType


class TestAjanisResponseProperties:
    """Static card data should match the SOS 6 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(AjanisResponse(owner=None), Instant)

    def test_name(self) -> None:
        assert AjanisResponse(owner=None).name == "Ajani's Response"

    def test_mana_cost(self) -> None:
        assert AjanisResponse(owner=None).mana_cost == ManaCost.parse("{4}{W}")


class TestAjanisResponseTargeting:
    """get_targets() should require a single creature target."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = AjanisResponse(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = AjanisResponse(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = AjanisResponse(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestAjanisResponseCostReduction:
    """Spell costs {3} less when targeting a tapped creature."""

    def test_cost_reduction_when_target_is_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = AjanisResponse(owner=p1, controller=p1)
        tapped_creature = Creature(
            name="Tapped Bear", owner=p1, base_power=2, base_toughness=2
        )
        tapped_creature.is_tapped = True
        tapped_creature.card_types = {CardType.CREATURE}
        spell.chosen_targets = [tapped_creature]
        reduction = spell.cost_reduction(game)
        assert reduction == 3

    def test_no_cost_reduction_when_target_is_untapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = AjanisResponse(owner=p1, controller=p1)
        untapped_creature = Creature(
            name="Untapped Bear", owner=p1, base_power=2, base_toughness=2
        )
        untapped_creature.is_tapped = False
        untapped_creature.card_types = {CardType.CREATURE}
        spell.chosen_targets = [untapped_creature]
        reduction = spell.cost_reduction(game)
        assert reduction == 0


class TestAjanisResponseResolution:
    """on_resolve destroys target creature."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = AjanisResponse(owner=p1, controller=p1)
        target = Creature(
            name="Doomed Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        # Target should no longer be on the battlefield
        assert target not in game.get_battlefield(p2).get_all()

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = AjanisResponse(owner=p1, controller=p1)
        # No chosen_targets — must not raise
        spell.on_resolve(game)

    def test_can_cast_for_two_mana_on_tapped_creature(self) -> None:
        """With cost reduction, total cost is {1}{W} (CMC 2)."""
        game = create_game()
        p1 = game.players[0]
        tapped = Creature(
            name="Tapped Target", owner=p1, controller=p1,
            base_power=3, base_toughness=3,
        )
        tapped.is_tapped = True
        tapped.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(tapped)
        spell = AjanisResponse(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Ajani's Response", targets=[tapped])
        assert tapped not in game.get_battlefield(p1).get_all()
