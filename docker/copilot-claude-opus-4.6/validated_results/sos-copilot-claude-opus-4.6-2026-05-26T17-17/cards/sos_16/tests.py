"""Tests for SOS 16 — Graduation Day.

Graduation Day is a {W} Enchantment with Repartee:
"Whenever you cast an instant or sorcery spell that targets a creature,
put a +1/+1 counter on target creature you control."
"""

from __future__ import annotations

import pytest
from cards.sos.sos_16.card_impl import GraduationDay
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestGraduationDayProperties:
    """Static card data should match the SOS 16 spec."""

    def test_name(self) -> None:
        assert GraduationDay(owner=None).name == "Graduation Day"

    def test_mana_cost(self) -> None:
        assert GraduationDay(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_card_type_is_enchantment(self) -> None:
        card = GraduationDay(owner=None)
        assert CardType.ENCHANTMENT in card.card_types


class TestGraduationDayRepartee:
    """Repartee trigger: casting an instant/sorcery targeting a creature
    should put a +1/+1 counter on a target creature you control."""

    def test_trigger_on_instant_targeting_creature(self) -> None:
        """When controller casts an instant targeting a creature,
        a +1/+1 counter is placed on a creature they control."""
        game = create_game()
        p1 = game.players[0]

        enchantment = GraduationDay(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[enchantment, bear],
                        mana={ManaType.WHITE: 5})

        # Create a targeting instant in hand
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt])

        # Cast the instant targeting the bear
        cast_spell(game, 0, "Test Bolt", targets=[bear])

        # Repartee should have triggered and put a +1/+1 counter
        assert bear.plus_one_counters >= 1

    def test_no_trigger_on_nontargeting_spell(self) -> None:
        """A spell that doesn't target a creature should not trigger Repartee."""
        game = create_game()
        p1 = game.players[0]

        enchantment = GraduationDay(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[enchantment, bear],
                        mana={ManaType.WHITE: 5})

        # Cast a non-targeting spell
        divination = Instant(name="Divination", owner=p1, controller=p1)
        divination.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[divination])
        cast_spell(game, 0, "Divination")

        assert bear.plus_one_counters == 0

    def test_counter_goes_on_creature_you_control(self) -> None:
        """The +1/+1 counter is placed on a creature the enchantment's
        controller controls, even if the spell targets opponent's creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        enchantment = GraduationDay(owner=p1, controller=p1)
        own_bear = Creature(
            name="Friendly Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        own_bear.card_types = {CardType.CREATURE}
        enemy_bear = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        enemy_bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[enchantment, own_bear],
                        mana={ManaType.WHITE: 5})
        set_board_state(game, 1, battlefield=[enemy_bear])

        bolt = Instant(name="Target Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt])

        cast_spell(game, 0, "Target Bolt", targets=[enemy_bear])

        # Counter goes on controller's creature, not on enemy
        assert own_bear.plus_one_counters >= 1
        assert enemy_bear.plus_one_counters == 0
