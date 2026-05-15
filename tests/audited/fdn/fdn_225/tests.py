"""Audited tests for FDN 225 — Grow from the Ashes."""

from __future__ import annotations

from card_impl import GrowFromTheAshes
from engine.card import CardImpl, Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone
from tests.test_utils import create_game


class TestGrowFromTheAshesBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GrowFromTheAshes(owner=None)
        assert card.name == "Grow from the Ashes"

    def test_mana_cost(self) -> None:
        card = GrowFromTheAshes(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_is_sorcery(self) -> None:
        card = GrowFromTheAshes(owner=None)
        assert isinstance(card, Sorcery)


class TestGrowFromTheAshesResolve:
    """Search for basic land(s) and put onto battlefield."""

    def test_finds_one_basic_land_not_kicked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = CardImpl(name="Forest", owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        land.supertypes = {Supertype.BASIC}
        p1.zones[Zone.LIBRARY].add(land)
        spell = GrowFromTheAshes(owner=p1, controller=p1)
        spell.kicked = False
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Forest" in bf_names

    def test_finds_two_basic_lands_when_kicked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land1 = CardImpl(name="Forest", owner=p1, controller=p1)
        land1.card_types = {CardType.LAND}
        land1.supertypes = {Supertype.BASIC}
        land2 = CardImpl(name="Plains", owner=p1, controller=p1)
        land2.card_types = {CardType.LAND}
        land2.supertypes = {Supertype.BASIC}
        p1.zones[Zone.LIBRARY].add(land1)
        p1.zones[Zone.LIBRARY].add(land2)
        spell = GrowFromTheAshes(owner=p1, controller=p1)
        spell.kicked = True
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        bf_all = bf.get_all()
        land_count = sum(1 for c in bf_all if CardType.LAND in getattr(c, "card_types", set()))
        assert land_count == 2

    def test_no_basic_lands_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = GrowFromTheAshes(owner=p1, controller=p1)
        spell.kicked = False
        spell.on_resolve(game)
        # Should not crash

