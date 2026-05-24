"""Audited tests for FDN 56 — Billowing Shriekmass."""

from __future__ import annotations

from card_impl import BillowingShriekmass
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBillowingShriekmassBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert card.name == "Billowing Shriekmass"

    def test_mana_cost(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = BillowingShriekmass(owner=None)
        assert "Spirit" in card.subtypes


class TestBillowingShriekmassETB:
    """ETB: mill three cards."""

    def test_mills_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BillowingShriekmass(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f"Card{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        card.on_resolve(game)
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        assert lib_before - lib_after == 3

    def test_milled_cards_go_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BillowingShriekmass(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f"Card{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(p1.zones[Zone.GRAVEYARD].get_all())
        assert gy_after - gy_before == 3

    def test_mills_fewer_if_library_small(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BillowingShriekmass(owner=p1, controller=p1)
        c = Creature(name="Only", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 1


class TestBillowingShriekmassThreshold:
    """Threshold: +2/+1 if 7+ cards in graveyard."""

    def test_no_bonus_below_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BillowingShriekmass(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(6):
            c = Creature(name=f"GY{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        effects = card.apply_continuous_effect(game)
        assert len(effects) == 0

    def test_bonus_at_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BillowingShriekmass(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(7):
            c = Creature(name=f"GY{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        effects = card.apply_continuous_effect(game)
        assert len(effects) == 1
