"""Tests for SOS 5 — Transcendent Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_5.card_impl import TranscendentArchaic
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestTranscendentArchaicProperties:
    """Static card data should match the SOS 5 spec."""

    def test_is_creature_with_vigilance(self) -> None:
        card = TranscendentArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = TranscendentArchaic(owner=None)
        assert card.name == "Transcendent Archaic"
        assert card.mana_cost == ManaCost.parse("{7}")
        assert card.base_power == 6
        assert card.base_toughness == 6


class TestTranscendentArchaicConverge:
    """The controller may draw X, then discard two if cards were drawn."""

    def test_declining_the_draw_keeps_hand_and_graveyard_unchanged(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        keep = CardImpl(name="Keep", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[keep], graveyard=[])

        card = TranscendentArchaic(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U]
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == [keep]
        assert game.get_graveyard(p1).get_all() == []

    def test_accepting_the_draw_draws_x_then_discards_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        keep = CardImpl(name="Keep", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[keep], graveyard=[])

        draw_one = CardImpl(name="Draw One", owner=p1, controller=p1)
        draw_two = CardImpl(name="Draw Two", owner=p1, controller=p1)
        draw_three = CardImpl(name="Draw Three", owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        game.get_library(p1).add(draw_three)

        p1._script.append(True)
        p1._script.append(draw_three)
        p1._script.append(draw_two)

        card = TranscendentArchaic(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U, Color.B]
        card.on_resolve(game)

        assert set(game.get_hand(p1).get_all()) == {keep, draw_one}
        assert game.get_graveyard(p1).get_all() == [draw_three, draw_two]

    def test_zero_colors_does_not_force_any_draw_or_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        keep = CardImpl(name="Keep", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[keep], graveyard=[])

        card = TranscendentArchaic(owner=p1, controller=p1)
        card.colors_spent = []
        card.on_resolve(game)

        assert game.get_hand(p1).get_all() == [keep]
        assert game.get_graveyard(p1).get_all() == []
