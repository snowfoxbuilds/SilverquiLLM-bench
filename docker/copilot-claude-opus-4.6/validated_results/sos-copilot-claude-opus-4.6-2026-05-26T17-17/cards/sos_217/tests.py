"""Tests for SOS 217 — Quandrix Charm.

Quandrix Charm is a {G}{U} Instant with three modes:
- Counter target spell unless its controller pays {2}.
- Destroy target enchantment.
- Target creature has base power and toughness 5/5 until end of turn.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_217.card_impl import QuandrixCharm
from engine.card import Creature, Instant, Enchantment
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestQuandrixCharmProperties:
    """Static card data should match the SOS 217 spec."""

    def test_name(self) -> None:
        assert QuandrixCharm(owner=None).name == "Quandrix Charm"

    def test_mana_cost(self) -> None:
        assert QuandrixCharm(owner=None).mana_cost == ManaCost.parse("{G}{U}")

    def test_is_instant(self) -> None:
        assert isinstance(QuandrixCharm(owner=None), Instant)


class TestQuandrixCharmModes:
    """Quandrix Charm should offer three modes."""

    def test_has_three_modes(self) -> None:
        game = create_game()
        card = QuandrixCharm(owner=None)
        modes = card.get_modes(game)
        assert len(modes) == 3


class TestQuandrixCharmCounterMode:
    """Mode 1: Counter target spell unless its controller pays {2}."""

    def test_counters_spell_when_not_paid(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Create a spell on the stack for p2
        target_spell = Creature(name="Target Spell", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.put_on_stack(target_spell, controller=p2)
        
        charm = QuandrixCharm(owner=p1, controller=p1)
        charm.chosen_mode = 0
        charm.chosen_targets = [target_spell]
        charm.on_resolve(game)
        # Spell should be countered (moved to graveyard)
        assert target_spell.zone == Zone.GRAVEYARD


class TestQuandrixCharmDestroyEnchantmentMode:
    """Mode 2: Destroy target enchantment."""

    def test_destroys_enchantment(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ench = Enchantment(name="Test Enchantment", owner=p2, controller=p2)
        ench.card_types = {CardType.ENCHANTMENT}
        game.get_battlefield(p2).add(ench)

        charm = QuandrixCharm(owner=p1, controller=p1)
        charm.chosen_mode = 1
        charm.chosen_targets = [ench]
        charm.on_resolve(game)
        assert ench.zone == Zone.GRAVEYARD


class TestQuandrixCharmPumpMode:
    """Mode 3: Target creature has base power and toughness 5/5 until end of turn."""

    def test_sets_base_pt_to_5_5(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        charm = QuandrixCharm(owner=p1, controller=p1)
        charm.chosen_mode = 2
        charm.chosen_targets = [bear]
        charm.on_resolve(game)
        assert bear.base_power == 5
        assert bear.base_toughness == 5

    def test_pump_wears_off_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        charm = QuandrixCharm(owner=p1, controller=p1)
        charm.chosen_mode = 2
        charm.chosen_targets = [bear]
        charm.on_resolve(game)
        # End the turn
        game.end_turn()
        assert bear.base_power == 2
        assert bear.base_toughness == 2

    def test_pump_works_on_small_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        token = Creature(name="Saproling", owner=p1, controller=p1, base_power=1, base_toughness=1)
        token.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(token)

        charm = QuandrixCharm(owner=p1, controller=p1)
        charm.chosen_mode = 2
        charm.chosen_targets = [token]
        charm.on_resolve(game)
        assert token.base_power == 5
        assert token.base_toughness == 5
