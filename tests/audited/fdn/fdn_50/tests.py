"""Audited tests for FDN 50 — Skyship Buccaneer."""

from __future__ import annotations

from card_impl import SkyshipBuccaneer
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestSkyshipBuccaneerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert card.name == "Skyship Buccaneer"

    def test_mana_cost(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")

    def test_power_toughness(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = SkyshipBuccaneer(owner=None)
        assert "Human" in card.subtypes
        assert "Pirate" in card.subtypes


class TestSkyshipBuccaneerRaid:
    """Raid: ETB draw a card if you attacked this turn."""

    def test_draws_card_if_attacked_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkyshipBuccaneer(owner=p1, controller=p1)
        game.attacked_this_turn = True
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 1

    def test_no_draw_if_did_not_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkyshipBuccaneer(owner=p1, controller=p1)
        game.attacked_this_turn = False
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 0

    def test_draws_card_if_player_attacked_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkyshipBuccaneer(owner=p1, controller=p1)
        p1.attacked_this_turn = True
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 1
