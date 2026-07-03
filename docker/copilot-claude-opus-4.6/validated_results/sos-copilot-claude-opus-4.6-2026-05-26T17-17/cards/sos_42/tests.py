"""Tests for SOS 42 — Deluge Virtuoso.

Deluge Virtuoso is a 2/2 for {2}{U} with:
- ETB: tap target creature an opponent controls and put a stun counter on it.
- Opus: Whenever you cast an instant or sorcery, gets +1/+1 until end of turn.
  If 5+ mana was spent, gets +2/+2 instead.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_42.card_impl import DelugeVirtuoso
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestDelugeVirtuosoProperties:
    """Static card data should match the SOS 42 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(DelugeVirtuoso(owner=None), Creature)

    def test_name(self) -> None:
        assert DelugeVirtuoso(owner=None).name == "Deluge Virtuoso"

    def test_mana_cost(self) -> None:
        assert DelugeVirtuoso(owner=None).mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = DelugeVirtuoso(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestDelugeVirtuosoETB:
    """ETB: tap target creature an opponent controls and put a stun counter on it."""

    def test_etb_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DelugeVirtuoso(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1

    def test_etb_taps_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enemy = Creature(name="Enemy", owner=p2, controller=p2, base_power=3, base_toughness=3)
        enemy.card_types = {CardType.CREATURE}
        enemy.is_tapped = False
        game.get_battlefield(p2).add(enemy)

        card = DelugeVirtuoso(owner=p1, controller=p1)
        card.chosen_targets = [enemy]
        card.on_resolve(game)

        assert enemy.is_tapped is True

    def test_etb_puts_stun_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enemy = Creature(name="Enemy", owner=p2, controller=p2, base_power=3, base_toughness=3)
        enemy.card_types = {CardType.CREATURE}
        enemy.is_tapped = False
        game.get_battlefield(p2).add(enemy)

        card = DelugeVirtuoso(owner=p1, controller=p1)
        card.chosen_targets = [enemy]
        card.on_resolve(game)

        assert enemy.counters.get("stun", 0) >= 1


class TestDelugeVirtuosoOpus:
    """Opus trigger: +1/+1 on instant/sorcery cast, +2/+2 if 5+ mana spent."""

    def test_plus_one_on_cheap_spell(self) -> None:
        """Casting a spell costing less than 5 mana gives +1/+1."""
        game = create_game()
        p1 = game.players[0]
        virtuoso = DelugeVirtuoso(owner=p1, controller=p1)
        game.get_battlefield(p1).add(virtuoso)
        virtuoso.register_triggers(game)

        # Simulate casting an instant costing 1 mana
        cheap_spell = Instant(name="Cheap Spell", owner=p1, controller=p1)
        cheap_spell.mana_cost = ManaCost.parse("{U}")

        # Trigger the opus ability with mana_spent < 5
        game.notify_spell_cast(p1, cheap_spell, mana_spent=1)

        assert virtuoso.get_power(game) >= 3  # 2 base + 1
        assert virtuoso.get_toughness(game) >= 3

    def test_plus_two_on_expensive_spell(self) -> None:
        """Casting a spell costing 5+ mana gives +2/+2 instead."""
        game = create_game()
        p1 = game.players[0]
        virtuoso = DelugeVirtuoso(owner=p1, controller=p1)
        game.get_battlefield(p1).add(virtuoso)
        virtuoso.register_triggers(game)

        expensive_spell = Instant(name="Big Spell", owner=p1, controller=p1)
        expensive_spell.mana_cost = ManaCost.parse("{4}{U}")

        game.notify_spell_cast(p1, expensive_spell, mana_spent=5)

        assert virtuoso.get_power(game) >= 4  # 2 base + 2
        assert virtuoso.get_toughness(game) >= 4
