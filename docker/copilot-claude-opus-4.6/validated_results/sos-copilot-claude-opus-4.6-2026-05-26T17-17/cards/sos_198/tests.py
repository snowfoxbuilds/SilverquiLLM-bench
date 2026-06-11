"""Tests for SOS 198 — Kirol, History Buff // Pack a Punch."""

from __future__ import annotations

import pytest

from cards.sos.sos_198.card_impl import KirolHistoryBuffPackAPunch
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestKirolProperties:
    """Static card data should match the SOS 198 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(KirolHistoryBuffPackAPunch(owner=None), Creature)

    def test_name(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)
        assert card.name == "Kirol, History Buff"

    def test_mana_cost(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}{W}")

    def test_power_toughness(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_is_legendary(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)
        assert card.is_legendary is True


class TestKirolPreparedTrigger:
    """Kirol becomes prepared when cards leave the graveyard."""

    def test_becomes_prepared_when_card_leaves_graveyard(self) -> None:
        """When one or more cards leave the graveyard, Kirol becomes prepared."""
        game = create_game()
        p1 = game.players[0]

        kirol = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kirol)

        # Put a card in graveyard then exile it (leaves graveyard)
        dummy = Creature(name="Dummy", owner=p1, base_power=1, base_toughness=1)
        game.get_graveyard(p1).add(dummy)
        game.move_zone(dummy, Zone.EXILE)

        assert kirol.is_prepared is True

    def test_not_prepared_initially(self) -> None:
        """Kirol does not enter prepared."""
        game = create_game()
        p1 = game.players[0]

        kirol = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kirol)

        assert kirol.is_prepared is False

    def test_casting_spell_copy_unprepares(self) -> None:
        """Casting the spell copy unprepares Kirol."""
        game = create_game()
        p1 = game.players[0]

        kirol = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kirol)

        # Make kirol prepared
        dummy = Creature(name="Dummy", owner=p1, base_power=1, base_toughness=1)
        game.get_graveyard(p1).add(dummy)
        game.move_zone(dummy, Zone.EXILE)

        assert kirol.is_prepared is True

        # Cast the Pack a Punch copy
        set_board_state(game, 0, mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        kirol.cast_prepared_spell(game)

        assert kirol.is_prepared is False

    def test_multiple_cards_leaving_triggers_once(self) -> None:
        """Multiple cards leaving at once still results in one prepare."""
        game = create_game()
        p1 = game.players[0]

        kirol = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kirol)

        # Put multiple cards in graveyard and exile them
        d1 = Creature(name="Dummy1", owner=p1, base_power=1, base_toughness=1)
        d2 = Creature(name="Dummy2", owner=p1, base_power=1, base_toughness=1)
        game.get_graveyard(p1).add(d1)
        game.get_graveyard(p1).add(d2)
        game.move_zone(d1, Zone.EXILE)
        game.move_zone(d2, Zone.EXILE)

        assert kirol.is_prepared is True
