"""Regression tests for FDN 165 — Think Twice.

Think Twice is an instant with Flashback {2}{U}. The behavioural surface
Phase G (cadence alignment) fixes is its post-resolution zone: when cast
normally it goes to the graveyard, but when cast via **flashback** (from the
graveyard) it is exiled as it resolves (rule 702.34e) rather than returning to
the graveyard — which is what the GRE stream shows (graveyard -> exile), not a
graveyard round-trip. Both casts still resolve their "draw a card" effect.
"""

from __future__ import annotations

from cards.fdn.fdn_165.card_impl import ThinkTwice
from engine.card import Creature, Instant
from engine.casting import CastMode, cast_spell_free
from engine.stack import resolve_top_of_stack
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


def _library_card(name: str = "Blank"):
    return Creature(name=name, base_power=1, base_toughness=1)


class TestThinkTwiceProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ThinkTwice(owner=None), Instant)

    def test_flashback_cost(self) -> None:
        assert ThinkTwice(owner=None).flashback_cost == ManaCost.parse("{2}{U}")


class TestThinkTwiceFlashbackExile:
    def _game_with_flashbackable_think_twice(self):
        game = create_game()
        p1 = game.players[0]
        card = ThinkTwice(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        # A card to draw so on_resolve does not fail on an empty library.
        game.get_library(p1).add(_library_card())
        return game, p1, card

    def test_flashback_cast_exiles_on_resolution(self) -> None:
        game, p1, card = self._game_with_flashbackable_think_twice()

        cast_spell_free(game, p1, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        resolve_top_of_stack(game)

        assert game.get_exile(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)

    def test_flashback_cast_still_draws(self) -> None:
        game, p1, card = self._game_with_flashbackable_think_twice()
        hand_before = len(game.get_hand(p1))

        cast_spell_free(game, p1, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        resolve_top_of_stack(game)

        assert len(game.get_hand(p1)) == hand_before + 1

    def test_graveyard_cast_without_flashback_mode_keeps_graveyard(self) -> None:
        """Flashback is an explicit cast mode, never inferred: Think Twice
        free-cast from the graveyard WITHOUT selecting flashback still draws
        but returns to the graveyard — no silent exile."""
        game, p1, card = self._game_with_flashbackable_think_twice()

        cast_spell_free(game, p1, card, Zone.GRAVEYARD)
        resolve_top_of_stack(game)

        assert game.get_graveyard(p1).contains(card)
        assert not game.get_exile(p1).contains(card)

    def test_normal_resolution_goes_to_graveyard(self) -> None:
        """The disposition override is flashback-only: a normal on_resolve draws
        and (via the engine's cast path) the card would go to the graveyard.
        Here we assert the default disposition is unchanged for a from-exile
        free cast (cascade/Etali style), which must NOT exile."""
        game = create_game()
        p1 = game.players[0]
        card = ThinkTwice(owner=p1, controller=p1)
        set_board_state(game, 0)
        game.get_exile(p1).add(card)
        game.get_library(p1).add(_library_card())

        cast_spell_free(game, p1, card, Zone.EXILE)
        resolve_top_of_stack(game)

        # From exile without flashback (no graveyard flashback path) → default
        # non-permanent disposition is the graveyard, never a silent exile.
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_exile(p1).contains(card)
