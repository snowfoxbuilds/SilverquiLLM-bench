"""Tests for SOS 45 — Emeritus of Ideation // Ancestral Recall.

Front face: 5/5 for {3}{U}{U} with flying, ward {2}.
Enters prepared. Whenever it attacks, may exile 8 cards from graveyard
to become prepared again.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_45.card_impl import EmeritusOfIdeationAncestralRecall
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state, declare_attackers


class TestEmeritusProperties:
    """Static card data should match the SOS 45 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfIdeationAncestralRecall(owner=None), Creature)

    def test_name(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert card.name == "Emeritus of Ideation // Ancestral Recall"

    def test_mana_cost(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_ward(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert Keyword.WARD in card.keywords


class TestEmeritusEntersPrepared:
    """This creature enters prepared."""

    def test_enters_battlefield_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.is_prepared is True


class TestEmeritusAttackTrigger:
    """Whenever this creature attacks, may exile 8 cards from graveyard to become prepared."""

    def test_attack_trigger_with_enough_graveyard_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        card.is_prepared = False
        game.get_battlefield(p1).add(card)

        # Put 8 cards in graveyard
        from engine.card import Instant
        gy_cards = [Instant(name=f"Spell {i}", owner=p1) for i in range(8)]
        set_board_state(game, 0, graveyard=gy_cards)

        card.register_triggers(game)
        # Simulate attack trigger choosing to exile 8 cards
        game.notify_attack(card, exile_graveyard=True)

        # Should become prepared
        assert card.is_prepared is True
        # Graveyard should have 8 fewer cards
        assert len(list(game.get_graveyard(p1))) == 0

    def test_attack_trigger_without_enough_cards_does_not_prepare(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        card.is_prepared = False
        game.get_battlefield(p1).add(card)

        # Only 5 cards in graveyard (not enough)
        from engine.card import Instant
        gy_cards = [Instant(name=f"Spell {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, graveyard=gy_cards)

        card.register_triggers(game)
        game.notify_attack(card, exile_graveyard=True)

        # Cannot exile 8 cards, so does NOT become prepared
        assert card.is_prepared is False
