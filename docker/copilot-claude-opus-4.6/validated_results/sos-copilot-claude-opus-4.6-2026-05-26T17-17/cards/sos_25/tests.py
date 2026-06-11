"""Tests for SOS 25 — Practiced Offense.

A sorcery for {2}{W} that puts a +1/+1 counter on each creature target
player controls, then a target creature gains choice of double strike or
lifelink until end of turn. Has Flashback {1}{W}.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_25.card_impl import PracticedOffense
from engine.card import Creature, CardImpl
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestPracticedOffenseProperties:
    """Static card data should match the SOS 25 spec."""

    def test_name(self) -> None:
        card = PracticedOffense(owner=None)
        assert card.name == "Practiced Offense"

    def test_mana_cost(self) -> None:
        card = PracticedOffense(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_has_flashback(self) -> None:
        card = PracticedOffense(owner=None)
        assert Keyword.FLASHBACK in card.keywords

    def test_flashback_cost(self) -> None:
        card = PracticedOffense(owner=None)
        assert card.flashback_cost == ManaCost.parse("{1}{W}")


class TestPracticedOffenseResolution:
    """on_resolve puts +1/+1 counters on all creatures target player controls,
    and grants one creature double strike or lifelink."""

    def test_puts_counter_on_all_creatures(self) -> None:
        """Each creature target player controls gets a +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]

        bear1 = Creature(name="Bear A", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        bear1.card_types = {CardType.CREATURE}
        bear2 = Creature(name="Bear B", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        bear2.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)

        spell = PracticedOffense(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear1]  # target player, target creature
        spell.chosen_mode = "double_strike"
        spell.on_resolve(game)

        assert bear1.plus_one_counters >= 1
        assert bear2.plus_one_counters >= 1

    def test_target_creature_gains_double_strike(self) -> None:
        """Target creature gains double strike when that mode is chosen."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = PracticedOffense(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        spell.chosen_mode = "double_strike"
        spell.on_resolve(game)

        assert Keyword.DOUBLE_STRIKE in bear.keywords

    def test_target_creature_gains_lifelink(self) -> None:
        """Target creature gains lifelink when that mode is chosen."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = PracticedOffense(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        spell.chosen_mode = "lifelink"
        spell.on_resolve(game)

        assert Keyword.LIFELINK in bear.keywords

    def test_no_creatures_still_resolves(self) -> None:
        """If target player has no creatures, spell still resolves (no error)."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = PracticedOffense(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        spell.chosen_mode = "double_strike"
        # Should not raise
        spell.on_resolve(game)

    def test_flashback_exiles_after_resolve(self) -> None:
        """When cast via flashback, the card is exiled after resolution."""
        game = create_game()
        p1 = game.players[0]

        spell = PracticedOffense(owner=p1, controller=p1)
        spell.cast_from_graveyard = True  # Simulates flashback cast

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell.chosen_targets = [p1, bear]
        spell.chosen_mode = "double_strike"
        spell.on_resolve(game)

        # Card should be in exile, not graveyard
        assert spell.zone == Zone.EXILE
