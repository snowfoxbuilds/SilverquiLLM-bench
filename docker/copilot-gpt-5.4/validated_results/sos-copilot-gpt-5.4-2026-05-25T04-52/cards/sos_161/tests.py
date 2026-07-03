"""Tests for SOS 161 — Snarl Song."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_161.card_impl import SnarlSong
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


def _fractal_tokens(game: object, player: object) -> list[Creature]:
    return [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if getattr(permanent, "is_token", False)
    ]


class TestSnarlSongProperties:
    """Static card data should match the SOS 161 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SnarlSong(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = SnarlSong(owner=None)

        assert card.name == "Snarl Song"
        assert card.mana_cost == ManaCost.parse("{5}{G}")


class TestSnarlSongConverge:
    """Snarl Song should count unique colors spent for both tokens and life gain."""

    def test_without_colors_spent_it_creates_two_zero_zero_green_and_blue_fractals_and_gains_no_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        before_life = p1.life
        card = SnarlSong(owner=p1, controller=p1)

        card.colors_spent = []
        card.on_resolve(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 2
        for token in tokens:
            assert isinstance(token, Creature)
            assert "Fractal" in token.subtypes
            assert get_colors(token) == {Color.GREEN, Color.BLUE}
            assert token.plus_one_counters == 0
            assert token.power == 0
            assert token.toughness == 0
        assert p1.life == before_life

    def test_three_colors_spent_puts_three_counters_on_each_token_and_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        before_life = p1.life
        card = SnarlSong(owner=p1, controller=p1)

        card.colors_spent = [Color.GREEN, Color.BLUE, Color.RED]
        card.on_resolve(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 2
        for token in tokens:
            assert token.plus_one_counters == 3
            assert token.power == 3
            assert token.toughness == 3
        assert p1.life == before_life + 3

    def test_duplicate_colors_spent_only_count_once_for_counters_and_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        before_life = p1.life
        card = SnarlSong(owner=p1, controller=p1)

        card.colors_spent = [Color.GREEN, Color.GREEN, Color.BLUE]
        card.on_resolve(game)

        tokens = _fractal_tokens(game, p1)
        assert len(tokens) == 2
        for token in tokens:
            assert token.plus_one_counters == 2
            assert token.power == 2
            assert token.toughness == 2
        assert p1.life == before_life + 2
