"""Audited tests for FDN 77 — Zul Ashur, Lich Lord."""

from __future__ import annotations

from card_impl import ZulAshurLichLord
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestZulAshurLichLordBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert card.name == "Zul Ashur, Lich Lord"

    def test_mana_cost(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_power_toughness(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert "Zombie" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_is_legendary(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert "Legendary" in getattr(card, "supertypes", set())

    def test_has_ward(self) -> None:
        card = ZulAshurLichLord(owner=None)
        assert Keyword.WARD in card.keywords


class TestZulAshurLichLordAbility:
    """Tap ability: cast Zombie from graveyard this turn."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZulAshurLichLord(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_ability_tap_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZulAshurLichLord(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert abilities[0].tap_cost is True

    def test_marks_zombie_as_castable(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZulAshurLichLord(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        zombie = Creature(name="Zombie Warrior", subtypes={"Zombie", "Warrior"}, base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(zombie)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert getattr(zombie, "_castable_from_graveyard", False) is True

    def test_no_effect_without_zombie_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZulAshurLichLord(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Non-zombie creature
        non_zombie = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(non_zombie)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert not getattr(non_zombie, "_castable_from_graveyard", False)

    def test_no_crash_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZulAshurLichLord(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)  # Should not crash
