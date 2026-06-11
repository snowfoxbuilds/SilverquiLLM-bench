"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptCounterspell:
    """Mana Sculpt counters target spell."""

    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Create a target spell on the stack
        target_spell = Creature(name="Target Creature", owner=p2, controller=p2,
                                base_power=3, base_toughness=3)
        target_spell.mana_spent = 3  # simulate mana spent to cast

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # The target spell should be countered (moved to graveyard)
        assert target_spell.zone == Zone.GRAVEYARD


class TestManaSculptManaRefund:
    """If you control a Wizard, add colorless mana equal to mana spent."""

    def test_adds_colorless_mana_with_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Player 1 controls a Wizard
        wizard = Creature(name="Test Wizard", owner=p1, controller=p1,
                          base_power=1, base_toughness=1)
        wizard.subtypes = {"Wizard"}
        wizard.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[wizard])

        # Target spell that cost 4 mana
        target_spell = Creature(name="Big Creature", owner=p2, controller=p2,
                                base_power=4, base_toughness=4)
        target_spell.mana_spent = 4

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # Should schedule delayed trigger for next main phase adding 4 colorless
        delayed = game.get_delayed_triggers(p1)
        assert len(delayed) >= 1
        # The delayed trigger should produce colorless mana equal to mana_spent
        assert any(t.mana_amount == 4 for t in delayed)

    def test_no_mana_without_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Player 1 does NOT control a Wizard
        non_wizard = Creature(name="Bear", owner=p1, controller=p1,
                              base_power=2, base_toughness=2)
        non_wizard.subtypes = {"Bear"}
        non_wizard.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[non_wizard])

        target_spell = Creature(name="Target", owner=p2, controller=p2,
                                base_power=3, base_toughness=3)
        target_spell.mana_spent = 3

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # No delayed trigger for mana
        delayed = game.get_delayed_triggers(p1)
        assert len(delayed) == 0
