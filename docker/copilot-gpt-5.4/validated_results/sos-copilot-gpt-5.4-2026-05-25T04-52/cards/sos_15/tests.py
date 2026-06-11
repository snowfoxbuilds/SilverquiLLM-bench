"""Tests for SOS 15 — Erode."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_15.card_impl import Erode
from benchmarks.sos.workspace.engine.basic_lands import Plains
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Planeswalker
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestErodeProperties:
    """Static card data should match the SOS 15 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Erode(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Erode(owner=None)
        assert card.name == "Erode"
        assert card.mana_cost == ManaCost.parse("{W}")


class TestErodeTargeting:
    """Erode should target a creature or planeswalker on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = Erode(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_planeswalkers_only(self) -> None:
        game = create_game()
        req = Erode(owner=None).get_targets(game)[0]

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Visitor", starting_loyalty=3)
        non_target = CardImpl(name="Rock")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(planeswalker) is True
        assert req.filter_fn(non_target) is False


class TestErodeResolution:
    """Erode should destroy the target and offer a tapped basic land search."""

    def test_destroyed_creatures_controller_may_decline_the_search(self) -> None:
        game = create_game(scripts=([], [False]))
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        plains = Plains(owner=p2, controller=p2)
        spell = Erode(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p2).add(plains)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert game.get_library(p2).contains(plains)
        assert not game.get_battlefield(p2).contains(plains)

    def test_destroyed_planeswalkers_controller_may_search_a_basic_land_onto_the_battlefield_tapped(self) -> None:
        game = create_game(scripts=([], [True]))
        p1, p2 = game.players
        target = Planeswalker(
            name="Target Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=4,
        )
        plains = Plains(owner=p2, controller=p2)
        spell = Erode(owner=p1, controller=p1)
        p2._script.append(plains)
        game.get_battlefield(p2).add(target)
        game.get_library(p2).add(plains)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert game.get_battlefield(p2).contains(plains)
        assert not game.get_library(p2).contains(plains)
        assert plains.controller is p2
        assert Supertype.BASIC in plains.supertypes
        assert plains.is_tapped is True

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = Erode(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_graveyard(p2).get_all() == []
