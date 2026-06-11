"""Tests for SOS 213 — Proctor's Gaze.

Instant — {2}{G}{U}
Return up to one target nonland permanent to its owner's hand.
Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_213.card_impl import ProctorsGaze
from engine.card import Instant, Creature
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


class TestProctorsGazeProperties:
    """Static card data should match the SOS 213 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ProctorsGaze(owner=None), Instant)

    def test_name(self) -> None:
        assert ProctorsGaze(owner=None).name == "Proctor's Gaze"

    def test_mana_cost(self) -> None:
        assert ProctorsGaze(owner=None).mana_cost == ManaCost.parse("{2}{G}{U}")


class TestProctorsGazeBounce:
    """Return up to one target nonland permanent to its owner's hand."""

    def test_bounces_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Target Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(target)

        spell = ProctorsGaze(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target not in game.get_battlefield(p2)
        assert target in game.get_hand(p2)

    def test_up_to_one_allows_zero_targets(self) -> None:
        """'Up to one' means casting with no targets is legal."""
        game = create_game()
        p1 = game.players[0]

        spell = ProctorsGaze(owner=p1, controller=p1)
        spell.chosen_targets = []
        # Should not raise — zero targets is valid
        spell.on_resolve(game)


class TestProctorsGazeLandSearch:
    """Search library for a basic land, put onto battlefield tapped, then shuffle."""

    def test_puts_basic_land_on_battlefield_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Add a basic land to library
        from engine.card import CardImpl
        forest = CardImpl(name="Forest", owner=p1)
        forest.is_basic_land = True
        game.get_library(p1).append(forest)

        spell = ProctorsGaze(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

        bf = game.get_battlefield(p1)
        # Forest should be on battlefield
        lands = [c for c in bf if c.name == "Forest"]
        assert len(lands) == 1
        assert lands[0].is_tapped is True

    def test_library_is_shuffled_after_search(self) -> None:
        game = create_game()
        p1 = game.players[0]

        from engine.card import CardImpl
        forest = CardImpl(name="Forest", owner=p1)
        forest.is_basic_land = True
        game.get_library(p1).append(forest)

        spell = ProctorsGaze(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

        # Library should have been shuffled (shuffle flag set)
        assert game.library_was_shuffled(p1) is True

    def test_no_basic_land_in_library_still_resolves(self) -> None:
        """If no basic land is found, the spell still resolves (fail to find)."""
        game = create_game()
        p1 = game.players[0]

        # Empty library — no basic lands
        spell = ProctorsGaze(owner=p1, controller=p1)
        spell.chosen_targets = []
        # Should not raise
        spell.on_resolve(game)
