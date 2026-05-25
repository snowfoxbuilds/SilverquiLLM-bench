"""Audited tests for FDN 54 — Abyssal Harvester."""

from __future__ import annotations

from card_impl import AbyssalHarvester
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestAbyssalHarvesterBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AbyssalHarvester(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AbyssalHarvester(owner=None)
        assert card.name == "Abyssal Harvester"

    def test_mana_cost(self) -> None:
        card = AbyssalHarvester(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_power_toughness(self) -> None:
        card = AbyssalHarvester(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = AbyssalHarvester(owner=None)
        assert "Demon" in card.subtypes
        assert "Warlock" in card.subtypes


class TestAbyssalHarvesterAbility:
    """Tap ability: exile creature from graveyard, create token copy with Nightmare."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_ability_tap_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert abilities[0].tap_cost is True

    def test_exiles_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert not p2.zones[Zone.GRAVEYARD].contains(target)

    def test_creates_token_with_nightmare_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, "is_token", False)]
        assert len(tokens) == 1
        assert "Nightmare" in tokens[0].subtypes

    def test_exiles_other_nightmare_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        old_token = Creature(name="OldNightmare", subtypes={"Nightmare"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        old_token.is_token = True
        game.get_battlefield(p1).add(old_token)
        target = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        bf = game.get_battlefield(p1)
        assert not bf.contains(old_token)

    def test_no_effect_with_empty_graveyards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbyssalHarvester(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        bf_before = len(game.get_battlefield(p1).get_all())
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before
