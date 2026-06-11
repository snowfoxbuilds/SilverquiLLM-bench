"""Tests for SOS 10 — Dig Site Inventory.

{W} Sorcery. Put a +1/+1 counter on target creature you control.
It gains vigilance until end of turn.
Flashback {W}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_10.card_impl import DigSiteInventory
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestDigSiteInventoryProperties:
    """Static card data should match the SOS 10 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(DigSiteInventory(owner=None), Sorcery)

    def test_name(self) -> None:
        assert DigSiteInventory(owner=None).name == "Dig Site Inventory"

    def test_mana_cost(self) -> None:
        assert DigSiteInventory(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_has_flashback(self) -> None:
        card = DigSiteInventory(owner=None)
        assert Keyword.FLASHBACK in card.keywords


class TestDigSiteInventoryTargeting:
    """Targets a creature you control."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = DigSiteInventory(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = DigSiteInventory(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestDigSiteInventoryResolution:
    """on_resolve puts +1/+1 counter and grants vigilance."""

    def test_puts_counter_on_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = DigSiteInventory(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        before = bear.plus_one_counters
        spell.on_resolve(game)
        assert bear.plus_one_counters == before + 1

    def test_grants_vigilance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.keywords = Keyword(0)
        game.get_battlefield(p1).add(bear)

        spell = DigSiteInventory(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        assert Keyword.VIGILANCE in bear.keywords

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = DigSiteInventory(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise

    def test_full_cast_flow(self) -> None:
        """Cast via helper to verify integration."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Target Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = DigSiteInventory(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Dig Site Inventory", targets=[bear])
        assert bear.plus_one_counters >= 1
        assert Keyword.VIGILANCE in bear.keywords
