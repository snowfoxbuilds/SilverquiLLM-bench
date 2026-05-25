"""Audited tests for FDN 211 — Affectionate Indrik."""

from __future__ import annotations

from card_impl import AffectionateIndrik
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestAffectionateIndrikBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = AffectionateIndrik(owner=None)
        assert card.name == "Affectionate Indrik"

    def test_mana_cost(self) -> None:
        card = AffectionateIndrik(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{G}")

    def test_power_toughness(self) -> None:
        card = AffectionateIndrik(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = AffectionateIndrik(owner=None)
        assert isinstance(card, Creature)

    def test_subtypes(self) -> None:
        card = AffectionateIndrik(owner=None)
        assert "Beast" in card.subtypes


class TestAffectionateIndrikETB:
    """ETB fight trigger."""

    def test_fights_opponent_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        indrik = AffectionateIndrik(owner=p1, controller=p1)
        game.get_battlefield(p1).add(indrik)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        indrik.on_resolve(game)
        # Indrik takes 2 damage from bear's power
        assert indrik.damage_marked == 2

    def test_no_target_no_crash(self) -> None:
        game = create_game()
        p1 = game.players[0]
        indrik = AffectionateIndrik(owner=p1, controller=p1)
        game.get_battlefield(p1).add(indrik)
        # No opponent creatures — should not crash
        indrik.on_resolve(game)
        assert indrik.damage_marked == 0
