"""Tests for SOS 152 — Infirmary Healer // Stream of Life.

A split card: Creature side is a 2/3 Cat Cleric for {1}{G} that enters prepared.
Spell side is Stream of Life: {X}{G} sorcery that gains X life.
While prepared, you may cast a copy of its spell side (unpreparing the creature).
"""

from __future__ import annotations

import pytest

from cards.sos.sos_152.card_impl import InfirmaryHealerStreamOfLife
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestInfirmaryHealerProperties:
    """Static card data should match the SOS 152 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(InfirmaryHealerStreamOfLife(owner=None), Creature)

    def test_name(self) -> None:
        card = InfirmaryHealerStreamOfLife(owner=None)
        assert card.name == "Infirmary Healer // Stream of Life"

    def test_mana_cost(self) -> None:
        card = InfirmaryHealerStreamOfLife(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = InfirmaryHealerStreamOfLife(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestInfirmaryHealerPrepared:
    """The creature enters prepared and can cast a copy of Stream of Life."""

    def test_enters_prepared(self) -> None:
        """When entering the battlefield, the creature should be prepared."""
        game = create_game()
        p1 = game.players[0]
        healer = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        game.get_battlefield(p1).add(healer)
        healer.on_enter_battlefield(game)
        assert healer.is_prepared is True

    def test_casting_spell_unprepares(self) -> None:
        """After casting the spell copy, the creature becomes unprepared."""
        game = create_game()
        p1 = game.players[0]
        healer = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        game.get_battlefield(p1).add(healer)
        healer.is_prepared = True
        healer.cast_prepared_spell(game, x_value=3)
        assert healer.is_prepared is False

    def test_cannot_cast_when_unprepared(self) -> None:
        """If already unprepared, should not be able to cast the spell."""
        game = create_game()
        p1 = game.players[0]
        healer = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        game.get_battlefield(p1).add(healer)
        healer.is_prepared = False
        assert healer.can_cast_prepared_spell(game) is False

    def test_stream_of_life_gains_life(self) -> None:
        """Stream of Life gains X life for the controller."""
        game = create_game()
        p1 = game.players[0]
        healer = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        game.get_battlefield(p1).add(healer)
        healer.is_prepared = True
        initial_life = p1.life
        healer.cast_prepared_spell(game, x_value=5)
        assert p1.life == initial_life + 5
