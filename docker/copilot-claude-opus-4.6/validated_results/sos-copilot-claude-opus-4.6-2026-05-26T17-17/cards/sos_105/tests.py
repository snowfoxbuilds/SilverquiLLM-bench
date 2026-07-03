"""Tests for SOS 105 — Withering Curse.

A sorcery for {1}{B}{B}.
All creatures get -2/-2 until end of turn.
Infusion — If you gained life this turn, destroy all creatures instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_105.card_impl import WitheringCurse
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestWitheringCurseProperties:
    """Static card data should match the SOS 105 spec."""

    def test_is_sorcery(self) -> None:
        card = WitheringCurse(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert WitheringCurse(owner=None).name == "Withering Curse"

    def test_mana_cost(self) -> None:
        assert WitheringCurse(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")


class TestWitheringCurseResolution:
    """Base mode: all creatures get -2/-2 until end of turn."""

    def test_creatures_get_minus_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        big = Creature(name="Giant", owner=p2, controller=p2, base_power=5, base_toughness=5)
        big.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(big)

        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Bear (2/2) gets -2/-2 → 0/0, should die to SBA or be marked
        # Giant (5/5) gets -2/-2 → 3/3
        assert big.get_power(game) == 3
        assert big.get_toughness(game) == 3

    def test_small_creature_dies_to_minus_two(self) -> None:
        game = create_game()
        p1 = game.players[0]

        small = Creature(name="Servo", owner=p1, controller=p1, base_power=1, base_toughness=1)
        small.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(small)

        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)

        # 1/1 with -2/-2 should have toughness <= 0
        # Either it's removed by SBA or its toughness is -1
        bf = game.get_battlefield(p1)
        if small in bf.get_all():
            assert small.get_toughness(game) <= 0


class TestWitheringCurseInfusion:
    """Infusion: if life was gained this turn, destroy all creatures instead."""

    def test_with_life_gain_destroys_all(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        big = Creature(name="Giant", owner=p2, controller=p2, base_power=5, base_toughness=5)
        big.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(big)

        # Mark life gained this turn
        p1.life_gained_this_turn = 3

        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)

        # All creatures should be destroyed (moved to graveyard)
        bf_p1 = game.get_battlefield(p1)
        bf_p2 = game.get_battlefield(p2)
        assert bear not in bf_p1.get_all()
        assert big not in bf_p2.get_all()

    def test_without_life_gain_does_not_destroy_big_creature(self) -> None:
        """Without infusion, a 5/5 survives -2/-2."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        big = Creature(name="Giant", owner=p2, controller=p2, base_power=5, base_toughness=5)
        big.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(big)

        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Giant should still be on the battlefield (survives -2/-2)
        bf_p2 = game.get_battlefield(p2)
        assert big in bf_p2.get_all()
