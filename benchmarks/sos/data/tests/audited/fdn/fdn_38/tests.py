"""Audited tests for FDN 38 — Faebloom Trick."""

from __future__ import annotations

from card_impl import FaebloomTrick
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost
from test_utils import create_game


class TestFaebloomTrickBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = FaebloomTrick(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = FaebloomTrick(owner=None)
        assert card.name == "Faebloom Trick"

    def test_mana_cost(self) -> None:
        card = FaebloomTrick(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")


class TestFaebloomTrickResolve:
    """Create two 1/1 blue Faerie tokens with flying, then tap target."""

    def test_creates_two_faerie_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FaebloomTrick(owner=p1, controller=p1)
        card.chosen_targets = []
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        faeries = [c for c in bf.get_all() if getattr(c, "name", "") == "Faerie"]
        assert len(faeries) == 2

    def test_faerie_tokens_have_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FaebloomTrick(owner=p1, controller=p1)
        card.chosen_targets = []
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        faeries = [c for c in bf.get_all() if getattr(c, "name", "") == "Faerie"]
        for f in faeries:
            assert Keyword.FLYING in f.keywords

    def test_faerie_tokens_are_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FaebloomTrick(owner=p1, controller=p1)
        card.chosen_targets = []
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        faeries = [c for c in bf.get_all() if getattr(c, "name", "") == "Faerie"]
        for f in faeries:
            assert f.base_power == 1
            assert f.base_toughness == 1

    def test_taps_target_opponent_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(
            name="Enemy", base_power=3, base_toughness=3,
            owner=p2, controller=p2,
        )
        game.get_battlefield(p2).add(target)
        card = FaebloomTrick(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.tapped is True

    def test_no_crash_without_tap_target(self) -> None:
        """If no target for tap, tokens still created."""
        game = create_game()
        p1 = game.players[0]
        card = FaebloomTrick(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        faeries = [c for c in bf.get_all() if getattr(c, "name", "") == "Faerie"]
        assert len(faeries) == 2
