"""Audited tests for FDN 29 — Arcane Epiphany."""

from __future__ import annotations

from card_impl import ArcaneEpiphany
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestArcaneEpiphanyBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = ArcaneEpiphany(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ArcaneEpiphany(owner=None)
        assert card.name == "Arcane Epiphany"

    def test_mana_cost(self) -> None:
        card = ArcaneEpiphany(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")


class TestArcaneEpiphanyCostReduction:
    """This spell costs {1} less to cast if you control a Wizard."""

    def test_no_reduction_without_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArcaneEpiphany(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_reduction_with_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArcaneEpiphany(owner=p1, controller=p1)
        wizard = Creature(
            name="Test Wizard", subtypes={"Wizard"},
            base_power=1, base_toughness=1, owner=p1, controller=p1,
        )
        game.get_battlefield(p1).add(wizard)
        assert card.cost_reduction(game) == 1

    def test_reduction_caps_at_one(self) -> None:
        """Even with multiple wizards, reduction is only 1."""
        game = create_game()
        p1 = game.players[0]
        card = ArcaneEpiphany(owner=p1, controller=p1)
        for i in range(3):
            w = Creature(
                name=f"Wizard {i}", subtypes={"Wizard"},
                base_power=1, base_toughness=1, owner=p1, controller=p1,
            )
            game.get_battlefield(p1).add(w)
        assert card.cost_reduction(game) == 1


class TestArcaneEpiphanyResolve:
    """Draw three cards on resolve."""

    def test_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArcaneEpiphany(owner=p1, controller=p1)
        # Add cards to library
        for i in range(5):
            c = Creature(name=f"Card{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 3

    def test_draws_fewer_if_library_small(self) -> None:
        """If library has fewer than 3 cards, draw what's available."""
        game = create_game()
        p1 = game.players[0]
        card = ArcaneEpiphany(owner=p1, controller=p1)
        c = Creature(name="Only", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 1
