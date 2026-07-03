"""Tests for SOS 92 — Poisoner's Apprentice."""

from __future__ import annotations

import pytest

from cards.sos.sos_92.card_impl import PoisonersApprentice
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestPoisonersApprenticeProperties:
    """Static card data should match the SOS 92 spec."""

    def test_is_creature(self) -> None:
        card = PoisonersApprentice(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert PoisonersApprentice(owner=None).name == "Poisoner's Apprentice"

    def test_mana_cost(self) -> None:
        assert PoisonersApprentice(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = PoisonersApprentice(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = PoisonersApprentice(owner=None)
        assert "Orc" in card.subtypes
        assert "Warlock" in card.subtypes


class TestPoisonersApprenticeInfusion:
    """Infusion — ETB: target opponent creature gets -4/-4 if you gained life this turn."""

    def test_gives_minus_4_4_when_life_gained(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        apprentice = PoisonersApprentice(owner=p1, controller=p1)
        target = Creature(
            name="Hill Giant", owner=p2, controller=p2,
            base_power=3, base_toughness=3,
        )
        set_board_state(game, 0, hand=[apprentice], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[target])

        # Mark that controller gained life this turn
        p1.life_gained_this_turn = 2

        cast_spell(game, 0, "Poisoner's Apprentice", targets=[target])

        # Target should have -4/-4 until end of turn
        assert target.get_power(game) == 3 - 4  # -1
        assert target.get_toughness(game) == 3 - 4  # -1

    def test_no_effect_without_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        apprentice = PoisonersApprentice(owner=p1, controller=p1)
        target = Creature(
            name="Hill Giant", owner=p2, controller=p2,
            base_power=3, base_toughness=3,
        )
        set_board_state(game, 0, hand=[apprentice], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[target])

        # No life gained this turn
        p1.life_gained_this_turn = 0

        cast_spell(game, 0, "Poisoner's Apprentice", targets=[target])

        # Target should be unchanged
        assert target.get_power(game) == 3
        assert target.get_toughness(game) == 3

    def test_kills_small_creature(self) -> None:
        """A creature with toughness <= 4 should die from the -4/-4."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        apprentice = PoisonersApprentice(owner=p1, controller=p1)
        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, hand=[apprentice], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[target])

        p1.life_gained_this_turn = 1

        cast_spell(game, 0, "Poisoner's Apprentice", targets=[target])

        # Bear should be dead (toughness <= 0 means SBA destroys it)
        battlefield_p2 = game.get_battlefield(p2)
        assert not any(c.name == "Grizzly Bears" for c in battlefield_p2)
