"""Audited tests for FDN 250 — Burnished Hart."""

from __future__ import annotations

from card_impl import BurnishedHart
from engine.card import ArtifactCreature, CardImpl
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from tests.test_utils import create_game


class TestBurnishedHartBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = BurnishedHart(owner=None)
        assert card.name == "Burnished Hart"

    def test_mana_cost(self) -> None:
        card = BurnishedHart(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}")

    def test_power_toughness(self) -> None:
        card = BurnishedHart(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_is_artifact_creature(self) -> None:
        card = BurnishedHart(owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_elk_subtype(self) -> None:
        card = BurnishedHart(owner=None)
        assert "Elk" in card.subtypes


class TestBurnishedHartAbility:
    """{3}, Sacrifice: search for up to two basic lands tapped."""

    def test_has_activated_ability(self) -> None:
        card = BurnishedHart(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_requires_three_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hart = BurnishedHart(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hart)
        abilities = hart.get_activated_abilities()
        # With only 2 mana, should fail
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        assert not abilities[0].cost(game, hart)

    def test_ability_searches_basic_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hart = BurnishedHart(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hart)

        # Put basic lands in library
        basic1 = CardImpl(name="Plains", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        basic1.card_types = {CardType.LAND}
        basic1.supertypes = {Supertype.BASIC}
        basic1.is_basic_land = True
        basic2 = CardImpl(name="Forest", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        basic2.card_types = {CardType.LAND}
        basic2.supertypes = {Supertype.BASIC}
        basic2.is_basic_land = True
        p1.zones[Zone.LIBRARY].add(basic1)
        p1.zones[Zone.LIBRARY].add(basic2)

        # Give mana and activate
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        abilities = hart.get_activated_abilities()
        abilities[0].cost(game, hart)
        abilities[0].effect(game)

        # Both basics should be on battlefield tapped
        bf = game.get_battlefield(p1).get_all()
        lands_on_bf = [c for c in bf if getattr(c, "is_basic_land", False)]
        assert len(lands_on_bf) == 2
        for land in lands_on_bf:
            assert land.is_tapped is True

    def test_ability_puts_lands_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hart = BurnishedHart(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hart)

        basic = CardImpl(name="Island", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        basic.card_types = {CardType.LAND}
        basic.is_basic_land = True
        p1.zones[Zone.LIBRARY].add(basic)

        p1.mana_pool.add(ManaType.COLORLESS, 3)
        abilities = hart.get_activated_abilities()
        abilities[0].cost(game, hart)
        abilities[0].effect(game)

        bf = game.get_battlefield(p1).get_all()
        lands = [c for c in bf if getattr(c, "name", "") == "Island"]
        assert len(lands) == 1
        assert lands[0].is_tapped is True

