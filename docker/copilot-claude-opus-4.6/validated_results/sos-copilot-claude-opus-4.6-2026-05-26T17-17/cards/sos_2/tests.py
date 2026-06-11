"""Tests for SOS 2 — Rancorous Archaic.

Rancorous Archaic is a {5} colorless Creature - Avatar (2/2) with:
- Trample, Reach keywords
- Converge: enters with a +1/+1 counter for each color of mana spent to cast it.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_2.card_impl import RancorousArchaic
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestRancorousArchaicProperties:
    """Static card properties should match the card spec."""

    def test_is_creature(self) -> None:
        card = RancorousArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = RancorousArchaic(owner=None)
        assert card.name == "Rancorous Archaic"

    def test_mana_cost(self) -> None:
        card = RancorousArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}")

    def test_power_toughness(self) -> None:
        card = RancorousArchaic(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_trample(self) -> None:
        card = RancorousArchaic(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_reach(self) -> None:
        card = RancorousArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_subtypes_include_avatar(self) -> None:
        card = RancorousArchaic(owner=None)
        assert "Avatar" in card.subtypes


class TestRancorousArchaicConverge:
    """Converge: enters with +1/+1 counter per color of mana spent."""

    def test_zero_colors_gives_zero_counters(self) -> None:
        """Casting with all colorless mana yields no +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Rancorous Archaic")
        # Find the creature on battlefield
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Rancorous Archaic")
        assert creature.plus_one_counters == 0

    def test_one_color_gives_one_counter(self) -> None:
        """Casting with one color of mana yields 1 +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Rancorous Archaic")
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Rancorous Archaic")
        assert creature.plus_one_counters == 1

    def test_five_colors_gives_five_counters(self) -> None:
        """Casting with all five colors yields 5 +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.RED: 1,
            ManaType.GREEN: 1,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Rancorous Archaic")
        assert creature.plus_one_counters == 5

    def test_three_colors_gives_three_counters(self) -> None:
        """Casting with three colors yields 3 +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.RED: 1,
            ManaType.COLORLESS: 2,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Rancorous Archaic")
        assert creature.plus_one_counters == 3

    def test_power_reflects_counters(self) -> None:
        """Power should be base + counters after entering."""
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1,
            ManaType.GREEN: 1,
            ManaType.COLORLESS: 3,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Rancorous Archaic")
        # 2 base + 2 counters = 4/4
        assert creature.power == 4
        assert creature.toughness == 4
