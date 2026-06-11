"""Tests for SOS 87 — Lecturing Scornmage.

{B} Creature — Human Warlock 1/1
Repartee — Whenever you cast an instant or sorcery spell that targets a
creature, put a +1/+1 counter on this creature.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_87.card_impl import LecturingScornmage
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestLecturingScornmageProperties:
    """Static card data should match the SOS 87 spec."""

    def test_is_creature(self) -> None:
        card = LecturingScornmage(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert LecturingScornmage(owner=None).name == "Lecturing Scornmage"

    def test_mana_cost(self) -> None:
        assert LecturingScornmage(owner=None).mana_cost == ManaCost.parse("{B}")

    def test_power_and_toughness(self) -> None:
        card = LecturingScornmage(owner=None)
        assert card.power == 1
        assert card.toughness == 1


class TestLecturingScornmageRepartee:
    """Repartee trigger: casting instant/sorcery targeting a creature
    should put a +1/+1 counter on this creature."""

    def test_gains_counter_when_spell_targets_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]

        scornmage = LecturingScornmage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scornmage)

        # Simulate casting an instant that targets a creature
        target = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        spell = Instant(name="Test Spell", owner=p1, controller=p1)
        spell.chosen_targets = [target]

        before_counters = scornmage.plus_one_counters
        scornmage.on_trigger_spell_cast(game, spell)

        assert scornmage.plus_one_counters == before_counters + 1

    def test_no_counter_when_spell_does_not_target_creature(self) -> None:
        """A spell that targets a player (not a creature) should not trigger."""
        game = create_game()
        p1 = game.players[0]

        scornmage = LecturingScornmage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scornmage)

        # Spell targeting a player, not a creature
        spell = Instant(name="Shock Face", owner=p1, controller=p1)
        spell.chosen_targets = [game.players[1]]

        before_counters = scornmage.plus_one_counters
        scornmage.on_trigger_spell_cast(game, spell)

        assert scornmage.plus_one_counters == before_counters

    def test_multiple_triggers_stack(self) -> None:
        """Each qualifying spell should add a counter."""
        game = create_game()
        p1 = game.players[0]

        scornmage = LecturingScornmage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scornmage)

        target = Creature(
            name="Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        spell1 = Instant(name="Spell A", owner=p1, controller=p1)
        spell1.chosen_targets = [target]
        spell2 = Instant(name="Spell B", owner=p1, controller=p1)
        spell2.chosen_targets = [target]

        scornmage.on_trigger_spell_cast(game, spell1)
        scornmage.on_trigger_spell_cast(game, spell2)

        assert scornmage.plus_one_counters == 2
