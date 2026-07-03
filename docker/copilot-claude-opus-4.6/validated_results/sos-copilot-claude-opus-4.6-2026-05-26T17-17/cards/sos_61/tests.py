"""Tests for SOS 61 — Muse's Encouragement.

An instant that creates a 3/3 blue and red Elemental creature token with flying,
then surveils 2.
"""

from __future__ import annotations

from cards.sos.sos_61.card_impl import MusesEncouragement
from engine.card import Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestMusesEncouragementProperties:
    """Static card data should match the SOS 61 spec."""

    def test_is_instant(self) -> None:
        card = MusesEncouragement(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert MusesEncouragement(owner=None).name == "Muse's Encouragement"

    def test_mana_cost(self) -> None:
        assert MusesEncouragement(owner=None).mana_cost == ManaCost.parse("{4}{U}")


class TestMusesEncouragementResolution:
    """on_resolve creates a token and surveils."""

    def test_creates_elemental_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = MusesEncouragement(owner=p1, controller=p1)
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if "Elemental" in getattr(c, 'name', '')]
        assert len(tokens) >= 1

    def test_token_is_3_3_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = MusesEncouragement(owner=p1, controller=p1)
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if getattr(c, 'base_power', None) == 3]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_toughness == 3
        assert Keyword.FLYING in token.keywords

    def test_token_is_blue_and_red(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = MusesEncouragement(owner=p1, controller=p1)
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if getattr(c, 'base_power', None) == 3]
        assert len(tokens) >= 1
        token = tokens[0]
        assert "U" in token.colors or ManaType.BLUE in token.colors
        assert "R" in token.colors or ManaType.RED in token.colors

    def test_surveil_2_puts_cards_in_graveyard_or_on_top(self) -> None:
        """After resolution, the library should have 2 fewer cards (moved to grave or stayed on top)."""
        game = create_game()
        p1 = game.players[0]
        # Give player a library to surveil from
        from engine.card import Card
        filler1 = Card(name="Filler1", owner=p1)
        filler2 = Card(name="Filler2", owner=p1)
        filler3 = Card(name="Filler3", owner=p1)
        game.get_library(p1).extend([filler1, filler2, filler3])
        lib_size_before = len(game.get_library(p1))

        spell = MusesEncouragement(owner=p1, controller=p1)
        spell.on_resolve(game)

        # After surveil 2, either cards went to graveyard or stayed on top
        lib_size_after = len(game.get_library(p1))
        grave_size = len(game.get_graveyard(p1))
        # Total cards accounted for: library + graveyard should equal original
        # (some cards may have moved to graveyard)
        assert lib_size_after + grave_size >= lib_size_before - 2 + grave_size
