"""Audited tests for FDN 34 — Curator of Destinies."""

from __future__ import annotations

from card_impl import CuratorOfDestinies
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestCuratorOfDestiniesBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert card.name == "Curator of Destinies"

    def test_mana_cost(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")

    def test_power_toughness(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_sphinx_subtype(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert "Sphinx" in card.subtypes

    def test_uncounterable_flag(self) -> None:
        card = CuratorOfDestinies(owner=None)
        assert getattr(card, "uncounterable", False) is True


class TestCuratorETB:
    """ETB: Fact or Fiction pile split."""

    def test_etb_distributes_all_five_cards(self) -> None:
        """All 5 top library cards end up in hand or graveyard."""
        # Script: p1 picks first 2 cards for pile A (choose_card returns card, card, None)
        # p2 chooses pile A for hand (True)
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lib_cards = []
        for i in range(5):
            c = Creature(name=f"Top{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
            lib_cards.append(c)
        # Script p1: pick top cards[4], top cards[3], then None to stop
        p1._script.extend([lib_cards[4], lib_cards[3], None])
        # Script p2: choose pile A (yes)
        p2._script.append(True)
        curator = CuratorOfDestinies(owner=p1, controller=p1)
        curator.on_resolve(game)
        hand_count = len(list(p1.zones[Zone.HAND].get_all()))
        gy_count = len(list(p1.zones[Zone.GRAVEYARD].get_all()))
        # All 5 cards should be distributed between hand and graveyard
        assert hand_count + gy_count == 5

    def test_etb_empty_library_no_crash(self) -> None:
        """If library is empty, ETB does nothing."""
        game = create_game()
        p1 = game.players[0]
        curator = CuratorOfDestinies(owner=p1, controller=p1)
        curator.on_resolve(game)  # Should not raise
