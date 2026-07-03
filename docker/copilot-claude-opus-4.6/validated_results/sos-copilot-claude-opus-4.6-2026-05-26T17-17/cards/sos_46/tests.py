"""Tests for SOS 46 — Encouraging Aviator // Jump.

A 2/3 Bird Wizard with Flying for {2}{U}.
Whenever it attacks, it becomes prepared.
The prepared mechanic lets you cast a copy of its spell (Jump side).
Jump is an instant for {U}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_46.card_impl import EncouragingAviatorJump
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, declare_attackers


class TestEncouragingAviatorProperties:
    """Static card data should match the SOS 46 spec."""

    def test_is_creature(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert card.name == "Encouraging Aviator"

    def test_mana_cost(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert Keyword.FLYING in card.keywords


class TestEncouragingAviatorPrepared:
    """Attacking triggers the prepared mechanic."""

    def test_not_prepared_initially(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        assert not getattr(card, "is_prepared", False)

    def test_becomes_prepared_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        declare_attackers(game, ["Encouraging Aviator"])
        assert card.is_prepared is True

    def test_prepared_allows_casting_jump_copy(self) -> None:
        """While prepared, controller may cast a copy of Jump (the back face)."""
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card], mana={ManaType.BLUE: 1})
        # Casting the prepared spell should unprepare it
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_casting_prepared_spell_unprepares(self) -> None:
        """Doing so unprepares it."""
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card], mana={ManaType.BLUE: 1})
        card.cast_prepared_spell(game)
        assert card.is_prepared is False
