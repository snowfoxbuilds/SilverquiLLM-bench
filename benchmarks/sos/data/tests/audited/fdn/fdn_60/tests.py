"""Audited tests for FDN 60 — Gutless Plunderer."""

from __future__ import annotations

from card_impl import GutlessPlunderer
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game


class TestGutlessPlundererBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert card.name == "Gutless Plunderer"

    def test_mana_cost(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_deathtouch(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_subtypes(self) -> None:
        card = GutlessPlunderer(owner=None)
        assert "Skeleton" in card.subtypes
        assert "Pirate" in card.subtypes


class TestGutlessPlundererRaid:
    """Raid ETB: look at top 3, keep one on top, mill the rest."""

    def test_no_trigger_without_raid(self) -> None:
        """If attacked_this_turn is False, does nothing."""
        game = create_game()
        p1 = game.players[0]
        card = GutlessPlunderer(owner=p1, controller=p1)
        p1.attacked_this_turn = False
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        card.on_resolve(game)
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        assert lib_after == lib_before

    def test_raid_mills_two_keeps_one(self) -> None:
        """With raid, top 3 looked at: 1 kept on top, 2 go to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = GutlessPlunderer(owner=p1, controller=p1)
        p1.attacked_this_turn = True
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        card.on_resolve(game)
        lib_after = len(p1.zones[Zone.LIBRARY].get_all())
        gy_after = len(p1.zones[Zone.GRAVEYARD].get_all())
        # 2 cards go to graveyard, 1 stays on top
        assert lib_before - lib_after == 2
        assert gy_after == 2

    def test_raid_with_fewer_than_three_cards(self) -> None:
        """If library has fewer than 3 cards, work with what's available."""
        game = create_game()
        p1 = game.players[0]
        card = GutlessPlunderer(owner=p1, controller=p1)
        p1.attacked_this_turn = True
        c = Creature(name="Only", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        # With 1 card, it may stay on top or go to graveyard
        total = len(p1.zones[Zone.LIBRARY].get_all()) + len(p1.zones[Zone.GRAVEYARD].get_all())
        assert total == 1
