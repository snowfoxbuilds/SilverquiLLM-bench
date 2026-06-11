"""Tests for SOS 21 — Inkshape Demonstrator.

A 3/4 Elephant Cleric with Ward {2} and Repartee (whenever you cast an
instant or sorcery spell that targets a creature, this creature gets +1/+0
and gains lifelink until end of turn).
"""

from __future__ import annotations

import pytest

from cards.sos.sos_21.card_impl import InkshapeDemonstrator
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestInkshapeDemonstratorProperties:
    """Static card data should match the SOS 21 spec."""

    def test_name(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert card.name == "Inkshape Demonstrator"

    def test_mana_cost(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}")

    def test_is_creature(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_ward(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert Keyword.WARD in card.keywords


class TestInkshapeDemonstratorWard:
    """Ward {2} — counter opponent's targeting spell unless they pay {2}."""

    def test_ward_cost_is_two(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        # Ward cost should be recorded as generic 2
        assert card.ward_cost == ManaCost.parse("{2}")


class TestInkshapeDemonstratorRepartee:
    """Repartee — triggers when controller casts an instant/sorcery targeting a creature."""

    def test_repartee_grants_plus_one_power(self) -> None:
        """Casting a creature-targeting instant gives +1/+0 until end of turn."""
        game = create_game()
        p1 = game.players[0]

        demonstrator = InkshapeDemonstrator(owner=p1, controller=p1)
        demonstrator.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(demonstrator)

        # A target creature to aim the spell at
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        # Simulate casting an instant targeting a creature
        # The repartee trigger should fire, giving +1/+0 and lifelink
        power_before = demonstrator.get_power(game)

        # Fire the repartee trigger directly
        demonstrator.on_repartee_trigger(game, bear)

        power_after = demonstrator.get_power(game)
        assert power_after == power_before + 1

    def test_repartee_grants_lifelink(self) -> None:
        """Repartee trigger grants lifelink until end of turn."""
        game = create_game()
        p1 = game.players[0]

        demonstrator = InkshapeDemonstrator(owner=p1, controller=p1)
        demonstrator.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(demonstrator)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        demonstrator.on_repartee_trigger(game, bear)

        assert Keyword.LIFELINK in demonstrator.keywords

    def test_repartee_stacks_multiple_triggers(self) -> None:
        """Multiple repartee triggers in one turn stack the +1/+0 bonus."""
        game = create_game()
        p1 = game.players[0]

        demonstrator = InkshapeDemonstrator(owner=p1, controller=p1)
        demonstrator.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(demonstrator)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        power_before = demonstrator.get_power(game)
        demonstrator.on_repartee_trigger(game, bear)
        demonstrator.on_repartee_trigger(game, bear)
        power_after = demonstrator.get_power(game)
        assert power_after == power_before + 2
