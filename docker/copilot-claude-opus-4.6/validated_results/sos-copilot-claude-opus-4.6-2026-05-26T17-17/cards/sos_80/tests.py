"""Tests for SOS 80 — Emeritus of Woe // Demonic Tutor.

A 5/4 creature for {3}{B} with Prepared. While prepared, can cast Demonic
Tutor (search library for a card, put in hand). At beginning of end step,
if two or more creatures died this turn, becomes prepared again.
"""

from __future__ import annotations

from cards.sos.sos_80.card_impl import EmeritusOfWoe
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestEmeritusOfWoeProperties:
    """Static card data should match the SOS 80 spec."""

    def test_name(self) -> None:
        card = EmeritusOfWoe(owner=None)
        assert card.name == "Emeritus of Woe"

    def test_mana_cost(self) -> None:
        card = EmeritusOfWoe(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfWoe(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = EmeritusOfWoe(owner=None)
        assert isinstance(card, Creature)

    def test_has_prepared_keyword(self) -> None:
        card = EmeritusOfWoe(owner=None)
        assert Keyword.PREPARED in card.keywords


class TestEmeritusOfWoePrepared:
    """Enters prepared and can cast Demonic Tutor."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoe(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.prepared is True

    def test_demonic_tutor_searches_library(self) -> None:
        """Casting prepared spell (Demonic Tutor) puts a card from library into hand."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoe(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        # Put a target card in library
        from engine.card import Card
        target_card = Card(name="Dark Ritual", owner=p1)
        game.get_library(p1).add(target_card)
        card.cast_prepared_spell(game, targets=[target_card])
        hand_names = [c.name for c in game.get_hand(p1).get_all()]
        assert "Dark Ritual" in hand_names

    def test_cast_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoe(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        from engine.card import Card
        target_card = Card(name="Dark Ritual", owner=p1)
        game.get_library(p1).add(target_card)
        card.cast_prepared_spell(game, targets=[target_card])
        assert card.prepared is False


class TestEmeritusOfWoeEndStepTrigger:
    """At end step, if 2+ creatures died this turn, becomes prepared again."""

    def test_becomes_prepared_if_two_creatures_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoe(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)
        # Simulate two creatures dying this turn
        game.creatures_died_this_turn = 2
        card.end_step_trigger(game)
        assert card.prepared is True

    def test_does_not_become_prepared_if_fewer_than_two_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoe(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)
        game.creatures_died_this_turn = 1
        card.end_step_trigger(game)
        assert card.prepared is False
