"""Audited tests for FDN 96 — Strongbox Raider."""

from __future__ import annotations

from card_impl import StrongboxRaider
from engine.card import Creature
from engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestStrongboxRaiderBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = StrongboxRaider(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = StrongboxRaider(owner=None)
        assert card.name == "Strongbox Raider"

    def test_mana_cost(self) -> None:
        card = StrongboxRaider(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}{R}")

    def test_power_toughness(self) -> None:
        card = StrongboxRaider(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = StrongboxRaider(owner=None)
        assert "Orc" in card.subtypes
        assert "Pirate" in card.subtypes


class TestStrongboxRaiderRaid:
    """Raid — ETB exile top 2 of library, choose one playable."""

    def test_exiles_two_cards_when_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrongboxRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        lib_before = len(list(p1.zones[Zone.LIBRARY].get_all()))
        # Script the choose_card call
        p1._script.appendleft(None)  # will be overridden by impl choosing first
        card.on_resolve(game)
        lib_after = len(list(p1.zones[Zone.LIBRARY].get_all()))
        assert lib_before - lib_after == 2

    def test_no_exile_when_not_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrongboxRaider(owner=p1, controller=p1)
        game.attacked_this_turn = False
        p1.attacked_this_turn = False
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        lib_before = len(list(p1.zones[Zone.LIBRARY].get_all()))
        card.on_resolve(game)
        lib_after = len(list(p1.zones[Zone.LIBRARY].get_all()))
        assert lib_before == lib_after

    def test_exiles_one_if_library_has_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrongboxRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        c = Creature(name="Only", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        lib_after = len(list(p1.zones[Zone.LIBRARY].get_all()))
        assert lib_after == 0

    def test_marks_chosen_card_playable(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrongboxRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        c1 = Creature(name="Card1", base_power=1, base_toughness=1, owner=p1)
        c2 = Creature(name="Card2", base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        # Script to choose first card offered
        p1._script.appendleft(c2)  # c2 is top of library (last added)
        card.on_resolve(game)
        assert getattr(c2, "_playable_until_next_turn", False) is True

    def test_no_crash_on_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrongboxRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        card.on_resolve(game)  # Should not crash
