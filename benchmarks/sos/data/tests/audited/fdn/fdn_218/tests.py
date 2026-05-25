"""Audited tests for FDN 218 — Dwynen's Elite."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost
from test_utils import create_game

# Direct import since conftest name mapping doesn't match (apostrophe)
_spec = importlib.util.spec_from_file_location(
    "fdn_218_impl",
    str(Path(__file__).resolve().parent.parent.parent.parent.parent / "cards" / "fdn" / "fdn_218" / "card_impl.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_mod.CardImpl = CardImpl  # type: ignore
_spec.loader.exec_module(_mod)  # type: ignore
DwynensElite = _mod.DwynensElite


class TestDwynensEliteBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = DwynensElite(owner=None)
        assert card.name == "Dwynen's Elite"

    def test_mana_cost(self) -> None:
        card = DwynensElite(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = DwynensElite(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = DwynensElite(owner=None)
        assert "Elf" in card.subtypes
        assert "Warrior" in card.subtypes


class TestDwynensEliteETB:
    """ETB: create token if you control another Elf."""

    def test_creates_token_with_other_elf(self) -> None:
        game = create_game()
        p1 = game.players[0]
        elite = DwynensElite(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elite)
        other_elf = Creature(name="Elf", base_power=1, base_toughness=1, subtypes={"Elf"}, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other_elf)
        elite.on_resolve(game)
        bf = game.get_battlefield(p1)
        all_cards = bf.get_all()
        tokens = [c for c in all_cards if getattr(c, "is_token", False)]
        assert len(tokens) == 1
        assert tokens[0].name == "Elf Warrior"
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1

    def test_no_token_without_other_elf(self) -> None:
        game = create_game()
        p1 = game.players[0]
        elite = DwynensElite(owner=p1, controller=p1)
        game.get_battlefield(p1).add(elite)
        # No other elf on battlefield
        elite.on_resolve(game)
        bf = game.get_battlefield(p1)
        all_cards = bf.get_all()
        tokens = [c for c in all_cards if getattr(c, "is_token", False)]
        assert len(tokens) == 0

