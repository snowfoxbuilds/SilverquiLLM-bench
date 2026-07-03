"""Tests for SOS 89 — Masterful Flourish.

{B} Instant: Target creature you control gets +1/+0 and gains indestructible
until end of turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_89.card_impl import MasterfulFlourish
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMasterfulFlourishProperties:
    """Static card data should match the SOS 89 spec."""

    def test_is_instant(self) -> None:
        card = MasterfulFlourish(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert MasterfulFlourish(owner=None).name == "Masterful Flourish"

    def test_mana_cost(self) -> None:
        assert MasterfulFlourish(owner=None).mana_cost == ManaCost.parse("{B}")


class TestMasterfulFlourishTargeting:
    """Targeting: must target a creature you control."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = MasterfulFlourish(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = MasterfulFlourish(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestMasterfulFlourishResolution:
    """on_resolve grants +1/+0 and indestructible until end of turn."""

    def test_grants_power_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]

        target = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        spell = MasterfulFlourish(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.power == 3  # 2 + 1
        assert target.toughness == 2  # unchanged

    def test_grants_indestructible(self) -> None:
        game = create_game()
        p1 = game.players[0]

        target = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        spell = MasterfulFlourish(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert Keyword.INDESTRUCTIBLE in target.keywords

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = MasterfulFlourish(owner=p1, controller=p1)
        spell.on_resolve(game)
