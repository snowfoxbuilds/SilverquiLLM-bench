"""Tests for SOS 195 — Imperious Inkmage."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_195.card_impl import ImperiousInkmage
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestImperiousInkmageProperties:
    """Static card data should match the SOS 195 spec."""

    def test_is_orc_warlock_with_vigilance(self) -> None:
        card = ImperiousInkmage(owner=None)

        assert isinstance(card, Creature)
        assert "Orc" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ImperiousInkmage(owner=None)

        assert card.name == "Imperious Inkmage"
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestImperiousInkmageSurveil:
    """Imperious Inkmage should surveil 2 when it resolves."""

    def test_on_resolve_may_put_both_surveilled_cards_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([True, True])

        ImperiousInkmage(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_graveyard(p1).contains(middle)
        assert game.get_library(p1).get_all() == [bottom]

    def test_on_resolve_may_leave_both_surveilled_cards_on_top_of_the_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([False, False])

        ImperiousInkmage(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom, middle, top]

    def test_empty_library_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]

        ImperiousInkmage(owner=p1, controller=p1).on_resolve(game)

        assert game.get_library(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []
