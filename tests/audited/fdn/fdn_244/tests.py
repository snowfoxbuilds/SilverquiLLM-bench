"""Audited tests for FDN 244 — Progenitus."""

from __future__ import annotations

from card_impl import Progenitus
from engine.card import Creature
from engine.events import CreatureDiesReplacementEvent
from engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestProgenitusBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = Progenitus(owner=None)
        assert card.name == "Progenitus"

    def test_mana_cost(self) -> None:
        card = Progenitus(owner=None)
        assert card.mana_cost == ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}")

    def test_power_toughness(self) -> None:
        card = Progenitus(owner=None)
        assert card.base_power == 10
        assert card.base_toughness == 10

    def test_is_legendary(self) -> None:
        card = Progenitus(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = Progenitus(owner=None)
        assert "Hydra" in card.subtypes
        assert "Avatar" in card.subtypes


class TestProgenitusProtection:
    """Protection from everything."""

    def test_has_protection(self) -> None:
        card = Progenitus(owner=None)
        assert len(card.protections) >= 1

    def test_protection_matches_any_source(self) -> None:
        card = Progenitus(owner=None)
        prot = card.protections[0]
        assert prot.predicate("anything") is True
        assert prot.predicate(42) is True


class TestProgenitusReplacementEffect:
    """Shuffle into library instead of going to graveyard."""

    def test_registers_replacement_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        prog = Progenitus(owner=p1, controller=p1)
        game.get_battlefield(p1).add(prog)
        prog.register_replacement_effects(game)
        event = CreatureDiesReplacementEvent(creature=prog)
        result = game.replacement_manager.apply(game, event)
        assert result.prevented is True
