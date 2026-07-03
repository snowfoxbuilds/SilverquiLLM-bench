"""Tests for SOS 118 — Heated Argument.

{4}{R} Instant.
Deals 6 damage to target creature.
You may exile a card from your graveyard. If you do, also deals 2 damage
to that creature's controller.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_118.card_impl import HeatedArgument
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestHeatedArgumentProperties:
    """Static card data should match the SOS 118 spec."""

    def test_is_instant(self) -> None:
        card = HeatedArgument(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert HeatedArgument(owner=None).name == "Heated Argument"

    def test_mana_cost(self) -> None:
        assert HeatedArgument(owner=None).mana_cost == ManaCost.parse("{4}{R}")


class TestHeatedArgumentResolution:
    """Deals 6 damage to target creature, optionally 2 to controller."""

    def test_deals_6_damage_to_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Big Beast", owner=p2, controller=p2,
            base_power=4, base_toughness=8
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # 6 damage to the creature
        assert target.damage_taken >= 6

    def test_exiling_graveyard_card_deals_2_to_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Big Beast", owner=p2, controller=p2,
            base_power=4, base_toughness=8
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        # Put a card in p1's graveyard to exile
        filler = Creature(name="Dead Thing", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[filler])

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        # Indicate that we choose to exile a card
        spell.exile_choice = filler
        spell.on_resolve(game)

        # 2 damage to the creature's controller
        assert p2.life <= 18  # started at 20, took 2

    def test_no_graveyard_card_means_no_bonus_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Big Beast", owner=p2, controller=p2,
            base_power=4, base_toughness=8
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        # No cards in graveyard
        set_board_state(game, 0, graveyard=[])

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # Controller takes no damage
        assert p2.life == 20

    def test_exiled_card_moves_to_exile_zone(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Big Beast", owner=p2, controller=p2,
            base_power=4, base_toughness=8
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        filler = Creature(name="Dead Thing", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[filler])

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.exile_choice = filler
        spell.on_resolve(game)

        # The card should no longer be in graveyard
        graveyard = game.get_graveyard(p1)
        assert filler not in graveyard.cards
