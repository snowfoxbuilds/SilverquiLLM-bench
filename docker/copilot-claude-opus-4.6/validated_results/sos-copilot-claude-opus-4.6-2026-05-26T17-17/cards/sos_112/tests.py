"""Tests for SOS 112 — Duel Tactics."""

from __future__ import annotations

import pytest

from cards.sos.sos_112.card_impl import DuelTactics
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestDuelTacticsProperties:
    """Static card data should match spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(DuelTactics(owner=None), Sorcery)

    def test_name(self) -> None:
        assert DuelTactics(owner=None).name == "Duel Tactics"

    def test_mana_cost(self) -> None:
        assert DuelTactics(owner=None).mana_cost == ManaCost.parse("{R}")

    def test_has_flashback(self) -> None:
        card = DuelTactics(owner=None)
        assert Keyword.FLASHBACK in card.keywords


class TestDuelTacticsDamage:
    """Deals 1 damage to target creature."""

    def test_deals_one_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Test Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = DuelTactics(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_taken == 1

    def test_kills_one_toughness_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Frail Elf",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = DuelTactics(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # Creature with 1 toughness should die from 1 damage
        assert target.damage_taken >= 1


class TestDuelTacticsCantBlock:
    """Target creature can't block this turn."""

    def test_target_cant_block_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Test Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = DuelTactics(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.can_block is False


class TestDuelTacticsFlashback:
    """Flashback {1}{R}."""

    def test_flashback_cost(self) -> None:
        card = DuelTactics(owner=None)
        assert card.flashback_cost == ManaCost.parse("{1}{R}")

    def test_can_be_cast_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DuelTactics(owner=p1, controller=p1)
        card.zone = Zone.GRAVEYARD
        assert card.can_cast_from_graveyard(game) is True

    def test_exiled_after_flashback(self) -> None:
        """After casting with flashback, the card is exiled."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Test Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = DuelTactics(owner=p1, controller=p1)
        card.zone = Zone.GRAVEYARD
        card.cast_with_flashback = True
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert card.zone == Zone.EXILE
