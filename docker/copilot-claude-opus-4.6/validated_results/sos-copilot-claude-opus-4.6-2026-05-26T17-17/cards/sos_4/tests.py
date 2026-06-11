"""Tests for SOS 4 — Together as One.

Together as One is a {6} colorless Sorcery with:
- Converge: Target player draws X cards, deals X damage to any target,
  and you gain X life, where X is the number of colors of mana spent.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestTogetherAsOneProperties:
    """Static card properties should match the card spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneConvergeEffect:
    """Converge: X = colors of mana spent. Draw X, deal X, gain X."""

    def test_zero_colors_does_nothing(self) -> None:
        """With 0 colors spent (all colorless), X=0: no draw, no damage, no life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        initial_life_p1 = game.players[0].life
        initial_life_p2 = game.players[1].life
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # No cards drawn, no damage, no life gained
        assert game.players[0].life == initial_life_p1
        assert game.players[1].life == initial_life_p2

    def test_one_color_draws_one_deals_one_gains_one(self) -> None:
        """With 1 color spent, X=1: draw 1, deal 1 damage, gain 1 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.RED: 1, ManaType.COLORLESS: 5})
        initial_life_p1 = game.players[0].life
        initial_life_p2 = game.players[1].life
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # Caster gains 1 life
        assert game.players[0].life == initial_life_p1 + 1
        # Damage target loses 1 life
        assert game.players[1].life == initial_life_p2 - 1

    def test_five_colors_draws_five_deals_five_gains_five(self) -> None:
        """With all 5 colors, X=5: draw 5, deal 5, gain 5."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.RED: 1,
            ManaType.GREEN: 1,
            ManaType.COLORLESS: 1,
        })
        initial_life_p1 = game.players[0].life
        initial_life_p2 = game.players[1].life
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # Caster gains 5 life
        assert game.players[0].life == initial_life_p1 + 5
        # Damage target loses 5 life
        assert game.players[1].life == initial_life_p2 - 5

    def test_damage_can_target_creature(self) -> None:
        """The damage portion can target a creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target_creature])
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.RED: 1,
            ManaType.GREEN: 1,
            ManaType.COLORLESS: 4,
        })
        cast_spell(game, 0, "Together as One", targets=[p1, target_creature])
        # 2 damage to creature (2 colors spent)
        assert target_creature.damage_marked == 2

    def test_three_colors_gains_three_life(self) -> None:
        """With 3 colors spent, caster gains 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.COLORLESS: 3,
        })
        initial_life = game.players[0].life
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert game.players[0].life == initial_life + 3
