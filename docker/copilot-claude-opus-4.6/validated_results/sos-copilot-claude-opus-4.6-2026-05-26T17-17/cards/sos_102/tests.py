"""Tests for SOS 102 — Tragedy Feaster.

A 7/6 Demon for {2}{B}{B} with Trample, Ward—Discard a card, and
Infusion — At the beginning of your end step, sacrifice a permanent
unless you gained life this turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_102.card_impl import TragedyFeaster
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTragedyFeasterProperties:
    """Static card data should match the SOS 102 spec."""

    def test_is_creature(self) -> None:
        card = TragedyFeaster(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert TragedyFeaster(owner=None).name == "Tragedy Feaster"

    def test_mana_cost(self) -> None:
        assert TragedyFeaster(owner=None).mana_cost == ManaCost.parse("{2}{B}{B}")

    def test_power_and_toughness(self) -> None:
        card = TragedyFeaster(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 6

    def test_has_trample(self) -> None:
        card = TragedyFeaster(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_ward(self) -> None:
        card = TragedyFeaster(owner=None)
        assert Keyword.WARD in card.keywords


class TestTragedyFeasterInfusion:
    """Infusion: at end step, sacrifice a permanent unless life was gained."""

    def test_no_life_gained_requires_sacrifice(self) -> None:
        """If controller did not gain life this turn, must sacrifice a permanent."""
        game = create_game()
        p1 = game.players[0]
        card = TragedyFeaster(owner=p1, controller=p1)
        token = Creature(name="Servo", owner=p1, controller=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, token])

        # Trigger end step without life gain
        card.on_end_step(game)

        # One permanent should have been sacrificed
        bf = game.get_battlefield(p1)
        total = len(bf.get_all())
        # Started with 2, should have sacrificed 1
        assert total <= 1

    def test_life_gained_no_sacrifice_needed(self) -> None:
        """If controller gained life this turn, no sacrifice required."""
        game = create_game()
        p1 = game.players[0]
        card = TragedyFeaster(owner=p1, controller=p1)
        token = Creature(name="Servo", owner=p1, controller=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, token])

        # Mark that life was gained this turn
        p1.life_gained_this_turn = 2

        card.on_end_step(game)

        bf = game.get_battlefield(p1)
        total = len(bf.get_all())
        assert total == 2  # Nothing sacrificed
