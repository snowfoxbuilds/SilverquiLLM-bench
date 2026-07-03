"""Tests for SOS 19 — Honorbound Page // Forum's Favor.

Front face: Honorbound Page — {3}{W} Creature — Cat Cleric 3/3
First strike. This creature enters prepared.

Back face: Forum's Favor — {W} Sorcery
(While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
"""

from __future__ import annotations

import pytest
from cards.sos.sos_19.card_impl import HonorboundPageForumsFavor
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestHonorboundPageProperties:
    """Static card data for the creature face."""

    def test_name(self) -> None:
        card = HonorboundPageForumsFavor(owner=None)
        assert card.name == "Honorbound Page"

    def test_mana_cost(self) -> None:
        card = HonorboundPageForumsFavor(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}")

    def test_is_creature(self) -> None:
        card = HonorboundPageForumsFavor(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = HonorboundPageForumsFavor(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_first_strike(self) -> None:
        card = HonorboundPageForumsFavor(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


class TestHonorboundPagePrepared:
    """The creature enters prepared; casting a copy of its spell unprepares it."""

    def test_enters_battlefield_prepared(self) -> None:
        """When Honorbound Page enters the battlefield, it is prepared."""
        game = create_game()
        p1 = game.players[0]

        card = HonorboundPageForumsFavor(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card],
                        mana={ManaType.WHITE: 1, ManaType.COLORLESS: 3})
        cast_spell(game, 0, "Honorbound Page")

        bf = game.get_battlefield(p1).get_all()
        page = [c for c in bf if c.name == "Honorbound Page"][0]
        assert page.prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        """After casting the spell copy, the creature becomes unprepared."""
        game = create_game()
        p1 = game.players[0]

        card = HonorboundPageForumsFavor(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card],
                        mana={ManaType.WHITE: 4, ManaType.COLORLESS: 3})
        cast_spell(game, 0, "Honorbound Page")

        bf = game.get_battlefield(p1).get_all()
        page = [c for c in bf if c.name == "Honorbound Page"][0]

        # Cast the spell copy (Forum's Favor)
        # The prepared ability lets us cast a copy of the spell side
        cast_spell(game, 0, "Forum's Favor")

        assert page.prepared is False

    def test_cannot_cast_spell_when_unprepared(self) -> None:
        """If already unprepared, cannot cast the spell copy again."""
        game = create_game()
        p1 = game.players[0]

        card = HonorboundPageForumsFavor(owner=p1, controller=p1)
        card.prepared = False
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.WHITE: 5})

        # Should not be able to cast Forum's Favor when unprepared
        with pytest.raises(Exception):
            cast_spell(game, 0, "Forum's Favor")
