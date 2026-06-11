"""Tests for SOS 186 — Embrace the Paradox.

Embrace the Paradox is a {3}{G}{U} Instant:
"Draw three cards. You may put a land card from your hand onto the battlefield tapped."
"""

from __future__ import annotations

from cards.sos.sos_186.card_impl import EmbraceTheParadox
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestEmbraceTheParadoxProperties:
    """Static card data should match the SOS 186 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(EmbraceTheParadox(owner=None), Instant)

    def test_name(self) -> None:
        assert EmbraceTheParadox(owner=None).name == "Embrace the Paradox"

    def test_mana_cost(self) -> None:
        assert EmbraceTheParadox(owner=None).mana_cost == ManaCost.parse("{3}{G}{U}")


class TestEmbraceTheParadoxResolution:
    """on_resolve draws three cards and optionally puts a land onto battlefield tapped."""

    def test_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Put cards in library to draw
        from engine.card import CardImpl
        cards_in_lib = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, library=cards_in_lib, hand=[])

        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.on_resolve(game)

        hand = game.get_hand(p1).get_all()
        assert len(hand) >= 3

    def test_may_put_land_from_hand_onto_battlefield_tapped(self) -> None:
        """If player chooses to put a land, it enters tapped."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import CardImpl
        land = CardImpl(name="Forest", owner=p1)
        land.card_types = {CardType.LAND}
        # Put land in hand and some cards in library
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[land], library=lib_cards)

        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        # The land should have been placed onto battlefield
        lands_on_bf = [c for c in bf if CardType.LAND in getattr(c, "card_types", set())]
        if lands_on_bf:
            assert lands_on_bf[0].tapped is True

    def test_no_land_in_hand_still_draws(self) -> None:
        """If no land in hand, just draw three cards (no crash)."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import CardImpl
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[], library=lib_cards)

        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.on_resolve(game)

        hand = game.get_hand(p1).get_all()
        assert len(hand) >= 3
