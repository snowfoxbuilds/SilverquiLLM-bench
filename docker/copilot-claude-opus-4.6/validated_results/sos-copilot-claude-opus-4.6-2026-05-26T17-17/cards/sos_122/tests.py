"""Tests for SOS 122 — Maelstrom Artisan // Rocket Volley."""

from __future__ import annotations

import pytest

from cards.sos.sos_122.card_impl import MaelstromArtisan
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestMaelstromArtisanProperties:
    """Static card data should match the SOS 122 spec."""

    def test_is_creature(self) -> None:
        card = MaelstromArtisan(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert MaelstromArtisan(owner=None).name == "Maelstrom Artisan"

    def test_mana_cost(self) -> None:
        assert MaelstromArtisan(owner=None).mana_cost == ManaCost.parse("{1}{R}{R}")

    def test_power_toughness(self) -> None:
        card = MaelstromArtisan(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_haste(self) -> None:
        card = MaelstromArtisan(owner=None)
        assert Keyword.HASTE in card.keywords


class TestMaelstromArtisanPrepared:
    """This creature enters prepared. While prepared, you may cast a copy of its spell."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[MaelstromArtisan(owner=None)],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Maelstrom Artisan")
        battlefield = game.get_battlefield(game.players[0])
        creature = next(c for c in battlefield if c.name == "Maelstrom Artisan")
        assert creature.is_prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MaelstromArtisan(owner=p1, controller=p1)
        card.is_prepared = True
        set_board_state(game, 0, battlefield=[card])
        # Use the prepared ability to cast Rocket Volley copy
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_cannot_cast_spell_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MaelstromArtisan(owner=p1, controller=p1)
        card.is_prepared = False
        set_board_state(game, 0, battlefield=[card])
        with pytest.raises(Exception):
            card.cast_prepared_spell(game)
