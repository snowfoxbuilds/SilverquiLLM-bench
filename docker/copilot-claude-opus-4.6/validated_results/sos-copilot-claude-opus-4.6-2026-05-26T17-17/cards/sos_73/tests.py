"""Tests for SOS 73 — Arcane Omens."""

from __future__ import annotations

import pytest

from cards.sos.sos_73.card_impl import ArcaneOmens
from engine.card import Sorcery, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestArcaneOmensProperties:
    """Static card data should match the SOS 73 spec."""

    def test_is_sorcery(self) -> None:
        card = ArcaneOmens(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ArcaneOmens(owner=None).name == "Arcane Omens"

    def test_mana_cost(self) -> None:
        assert ArcaneOmens(owner=None).mana_cost == ManaCost.parse("{4}{B}")


class TestArcaneOmensConverge:
    """Converge — target player discards X cards where X = colors of mana spent."""

    def test_one_color_discards_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = ArcaneOmens(owner=p1, controller=p1)
        # Simulate spending only black mana (1 color)
        spell.colors_of_mana_spent = 1

        # Give opponent cards in hand
        filler = [Creature(name=f"Card {i}", owner=p2, controller=p2,
                           base_power=1, base_toughness=1) for i in range(5)]
        set_board_state(game, 1, hand=filler)

        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        hand = game.get_hand(p2)
        assert len(hand) == 4  # discarded 1

    def test_five_colors_discards_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 5

        filler = [Creature(name=f"Card {i}", owner=p2, controller=p2,
                           base_power=1, base_toughness=1) for i in range(7)]
        set_board_state(game, 1, hand=filler)

        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        hand = game.get_hand(p2)
        assert len(hand) == 2  # discarded 5

    def test_zero_colors_discards_zero(self) -> None:
        """If somehow 0 colors spent (e.g. all colorless), no discard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 0

        filler = [Creature(name=f"Card {i}", owner=p2, controller=p2,
                           base_power=1, base_toughness=1) for i in range(3)]
        set_board_state(game, 1, hand=filler)

        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        hand = game.get_hand(p2)
        assert len(hand) == 3

    def test_discard_more_than_hand_discards_all(self) -> None:
        """If X > hand size, player discards their whole hand."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 5

        filler = [Creature(name=f"Card {i}", owner=p2, controller=p2,
                           base_power=1, base_toughness=1) for i in range(2)]
        set_board_state(game, 1, hand=filler)

        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        hand = game.get_hand(p2)
        assert len(hand) == 0
