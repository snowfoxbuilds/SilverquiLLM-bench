"""Tests for SOS 76 — Cheerful Osteomancer // Raise Dead.

A 4/2 creature for {3}{B} that enters prepared. While prepared, you may
cast a copy of its spell (Raise Dead — return a creature card from
graveyard to hand). Doing so unprepares it.
"""

from __future__ import annotations

from cards.sos.sos_76.card_impl import CheerfulOsteomancer
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestCheerfulOsteomancerProperties:
    """Static card data should match the SOS 76 spec."""

    def test_name(self) -> None:
        card = CheerfulOsteomancer(owner=None)
        assert card.name == "Cheerful Osteomancer"

    def test_mana_cost(self) -> None:
        card = CheerfulOsteomancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = CheerfulOsteomancer(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_is_creature(self) -> None:
        card = CheerfulOsteomancer(owner=None)
        assert isinstance(card, Creature)

    def test_has_prepared_keyword(self) -> None:
        card = CheerfulOsteomancer(owner=None)
        assert Keyword.PREPARED in card.keywords


class TestCheerfulOsteomancerPrepared:
    """Enters prepared and can cast Raise Dead (return creature from GY to hand)."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CheerfulOsteomancer(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.prepared is True

    def test_cast_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CheerfulOsteomancer(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        # Put a creature in graveyard as target for Raise Dead
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_graveyard(p1).add(bear)
        # Cast the prepared spell
        card.cast_prepared_spell(game, targets=[bear])
        assert card.prepared is False

    def test_raise_dead_returns_creature_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CheerfulOsteomancer(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        # Put a creature in graveyard
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_graveyard(p1).add(bear)
        # Cast the prepared spell (Raise Dead)
        card.cast_prepared_spell(game, targets=[bear])
        # Bear should now be in hand
        hand_names = [c.name for c in game.get_hand(p1).get_all()]
        assert "Grizzly Bears" in hand_names

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CheerfulOsteomancer(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(bear)
        # Should not be able to cast when not prepared
        result = card.cast_prepared_spell(game, targets=[bear])
        # Either raises or returns False/None indicating failure
        assert result is None or result is False
