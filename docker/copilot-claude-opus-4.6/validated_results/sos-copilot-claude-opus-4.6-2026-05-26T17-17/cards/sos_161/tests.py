"""Tests for SOS 161 — Snarl Song.

Snarl Song is a Sorcery costing {5}{G} with Converge:
- Create two 0/0 green and blue Fractal creature tokens
- Put X +1/+1 counters on each of them
- Gain X life
- Where X is the number of colors of mana spent to cast this spell
"""

from __future__ import annotations

from cards.sos.sos_161.card_impl import SnarlSong
from engine.card import Sorcery
from engine.types import ManaCost
from test_utils import create_game


class TestSnarlSongProperties:
    """Static card data should match the SOS 161 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SnarlSong(owner=None), Sorcery)

    def test_name(self) -> None:
        assert SnarlSong(owner=None).name == "Snarl Song"

    def test_mana_cost(self) -> None:
        assert SnarlSong(owner=None).mana_cost == ManaCost.parse("{5}{G}")


class TestSnarlSongResolution:
    """Converge — creates two Fractal tokens with counters and gains life."""

    def test_creates_two_fractal_tokens(self) -> None:
        """Should create exactly two creature tokens on resolution."""
        game = create_game()
        p1 = game.players[0]
        spell = SnarlSong(owner=p1, controller=p1)
        # Simulate spending 1 color of mana (just green)
        spell.colors_of_mana_spent = 1
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        assert len(tokens) == 2

    def test_fractal_tokens_are_green_and_blue(self) -> None:
        """Tokens should be green and blue."""
        game = create_game()
        p1 = game.players[0]
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 1
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        for token in tokens:
            assert "G" in token.colors
            assert "U" in token.colors

    def test_fractal_tokens_base_zero_zero(self) -> None:
        """Tokens should have base power/toughness 0/0."""
        game = create_game()
        p1 = game.players[0]
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 1
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        for token in tokens:
            assert token.base_power == 0
            assert token.base_toughness == 0

    def test_counters_equal_to_colors_spent(self) -> None:
        """Each token gets X +1/+1 counters where X = colors of mana spent."""
        game = create_game()
        p1 = game.players[0]
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 3
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        for token in tokens:
            assert token.plus_one_counters == 3

    def test_life_gain_equals_colors_spent(self) -> None:
        """Controller gains X life where X = colors of mana spent."""
        game = create_game()
        p1 = game.players[0]
        starting_life = p1.life
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 4
        spell.on_resolve(game)
        assert p1.life == starting_life + 4

    def test_single_color_gives_one_counter_and_one_life(self) -> None:
        """With only 1 color spent, X=1."""
        game = create_game()
        p1 = game.players[0]
        starting_life = p1.life
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 1
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        for token in tokens:
            assert token.plus_one_counters == 1
        assert p1.life == starting_life + 1

    def test_five_colors_maximum(self) -> None:
        """With all 5 colors spent, X=5."""
        game = create_game()
        p1 = game.players[0]
        starting_life = p1.life
        spell = SnarlSong(owner=p1, controller=p1)
        spell.colors_of_mana_spent = 5
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        for token in tokens:
            assert token.plus_one_counters == 5
        assert p1.life == starting_life + 5
