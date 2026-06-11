"""Tests for SOS 167 — Wild Hypothesis."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_167.card_impl import WildHypothesis
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


def _fractal_tokens(game: object, player: object) -> list[Creature]:
    return [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if getattr(permanent, "is_token", False)
    ]


class TestWildHypothesisProperties:
    """Static card data should match the SOS 167 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(WildHypothesis(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = WildHypothesis(owner=None)

        assert card.name == "Wild Hypothesis"
        assert card.mana_cost == ManaCost.parse("{X}{G}")


class TestWildHypothesisResolution:
    """Wild Hypothesis should make an X-sized Fractal and surveil 2."""

    def test_x_value_sets_the_fractal_tokens_counters_power_and_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = WildHypothesis(owner=p1, controller=p1)
        spell.x_value = 4  # type: ignore[attr-defined]

        spell.on_resolve(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 4
        assert token.power == 4
        assert token.toughness == 4

    def test_surveil_two_can_put_both_looked_at_cards_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([True, True])

        spell = WildHypothesis(owner=p1, controller=p1)
        spell.x_value = 0  # type: ignore[attr-defined]
        spell.on_resolve(game)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_graveyard(p1).contains(middle)
        assert game.get_library(p1).get_all() == [bottom]

    def test_surveil_two_can_leave_both_looked_at_cards_on_top_of_the_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        middle = CardImpl(name="Middle Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(middle)
        game.get_library(p1).add(top)
        p1._script.extend([False, False])

        spell = WildHypothesis(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        spell.on_resolve(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 1
        assert tokens[0].plus_one_counters == 2
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom, middle, top]
