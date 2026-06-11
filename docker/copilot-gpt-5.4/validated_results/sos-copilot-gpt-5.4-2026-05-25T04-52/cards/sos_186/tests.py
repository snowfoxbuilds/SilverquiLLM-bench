"""Tests for SOS 186 — Embrace the Paradox."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_186.card_impl import EmbraceTheParadox
from benchmarks.sos.workspace.engine.card import CardImpl, Instant, Land
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEmbraceTheParadoxProperties:
    """Static card data should match the SOS 186 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(EmbraceTheParadox(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = EmbraceTheParadox(owner=None)

        assert card.name == "Embrace the Paradox"
        assert card.mana_cost == ManaCost.parse("{3}{G}{U}")


class TestEmbraceTheParadoxResolution:
    """Embrace the Paradox should draw cards and optionally deploy a land."""

    def test_on_resolve_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        first = CardImpl(name="First Note", owner=p1, controller=p1)
        second = CardImpl(name="Second Note", owner=p1, controller=p1)
        third = CardImpl(name="Third Note", owner=p1, controller=p1)
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)

        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(first)
        assert game.get_hand(p1).contains(second)
        assert game.get_hand(p1).contains(third)
        assert game.get_battlefield(p1).get_all() == []

    def test_may_put_a_land_from_hand_onto_the_battlefield_tapped_without_using_a_land_play(self) -> None:
        game = create_game()
        p1 = game.players[0]
        campus = Land(name="Quandrix Campus", owner=p1, controller=p1)
        first = CardImpl(name="First Note", owner=p1, controller=p1)
        second = CardImpl(name="Second Note", owner=p1, controller=p1)
        third = CardImpl(name="Third Note", owner=p1, controller=p1)
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)
        set_board_state(game, 0, hand=[campus])
        p1._script.extend([True, campus])

        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_battlefield(p1).contains(campus)
        assert campus.is_tapped is True
        assert not game.get_hand(p1).contains(campus)
        assert p1.land_plays_remaining == 1
