"""Tests for SOS 51 — Fractalize."""

from __future__ import annotations

import pytest

from cards.sos.sos_51.card_impl import Fractalize
from engine.card import Creature, Instant
from engine.types import CardType, Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestFractalizeProperties:
    """Static card data should match the SOS 51 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Fractalize(owner=None), Instant)

    def test_name(self) -> None:
        assert Fractalize(owner=None).name == "Fractalize"

    def test_mana_cost(self) -> None:
        assert Fractalize(owner=None).mana_cost == ManaCost.parse("{X}{U}")


class TestFractalizeTargeting:
    """get_targets() advertises a single creature target."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = Fractalize(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = Fractalize(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = Fractalize(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestFractalizeResolution:
    """on_resolve sets base P/T to X+1, changes colors and creature types."""

    def test_base_power_toughness_set_to_x_plus_1(self) -> None:
        """With X=3, target becomes 4/4."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.subtypes = {"Bear"}
        game.get_battlefield(p1).add(bear)

        spell = Fractalize(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.x_value = 3
        spell.on_resolve(game)

        # Base P/T should be X+1 = 4
        assert bear.base_power == 4
        assert bear.base_toughness == 4

    def test_x_equals_zero_gives_1_1(self) -> None:
        """With X=0, target becomes 1/1."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Fractalize(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.x_value = 0
        spell.on_resolve(game)

        assert bear.base_power == 1
        assert bear.base_toughness == 1

    def test_creature_becomes_green_and_blue(self) -> None:
        """Target loses all other colors and becomes green and blue."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.colors = {Color.RED}
        game.get_battlefield(p1).add(bear)

        spell = Fractalize(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.x_value = 2
        spell.on_resolve(game)

        assert Color.GREEN in bear.colors
        assert Color.BLUE in bear.colors
        # Should only be green and blue
        assert len(bear.colors) == 2

    def test_creature_type_becomes_fractal(self) -> None:
        """Target loses all creature types and becomes a Fractal."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.subtypes = {"Bear"}
        game.get_battlefield(p1).add(bear)

        spell = Fractalize(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.x_value = 2
        spell.on_resolve(game)

        assert "Fractal" in bear.subtypes
        assert "Bear" not in bear.subtypes

    def test_no_target_is_noop(self) -> None:
        """Resolution with no target should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = Fractalize(owner=p1, controller=p1)
        spell.on_resolve(game)
