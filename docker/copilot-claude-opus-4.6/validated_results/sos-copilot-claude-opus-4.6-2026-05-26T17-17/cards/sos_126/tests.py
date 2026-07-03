"""Tests for SOS 126 — Pigment Wrangler // Striking Palette.

A split card: Creature side (4R, 4/4, Flying, enters prepared) and
Sorcery side (R). The prepared mechanic allows casting a copy of the
spell side while prepared, then unprepares.
"""

from __future__ import annotations

from cards.sos.sos_126.card_impl import PigmentWrangler
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestPigmentWranglerProperties:
    """Static card data should match the SOS 126 spec."""

    def test_name(self) -> None:
        card = PigmentWrangler(owner=None)
        assert card.name == "Pigment Wrangler"

    def test_is_creature(self) -> None:
        card = PigmentWrangler(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = PigmentWrangler(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}")

    def test_power_and_toughness(self) -> None:
        card = PigmentWrangler(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = PigmentWrangler(owner=None)
        assert Keyword.FLYING in card.keywords


class TestPigmentWranglerPrepared:
    """The creature enters prepared and can cast its spell side."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PigmentWrangler(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # After entering, the creature should be prepared
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PigmentWrangler(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.RED: 2})
        # Simulate using the prepared ability
        card.prepared = True
        card.use_prepared_ability(game)
        assert card.prepared is False

    def test_color_is_red(self) -> None:
        card = PigmentWrangler(owner=None)
        assert "R" in card.colors or ManaType.RED in card.colors
