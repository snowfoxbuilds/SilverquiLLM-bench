"""Audited tests for FDN 161 — Omniscience."""

from __future__ import annotations

from card_impl import Omniscience
from benchmarks.sos.workspace.engine.card import Enchantment
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestOmniscienceBasics:
    """Basic card properties."""

    def test_is_enchantment(self) -> None:
        card = Omniscience(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = Omniscience(owner=None)
        assert card.name == "Omniscience"

    def test_mana_cost(self) -> None:
        card = Omniscience(owner=None)
        assert card.mana_cost == ManaCost.parse("{7}{U}{U}{U}")

    def test_cmc_is_10(self) -> None:
        card = Omniscience(owner=None)
        assert card.mana_cost.cmc == 10


class TestOmniscienceEffect:
    """Cast spells from hand without paying mana costs."""

    def test_sets_omniscience_flag_on_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        omni = Omniscience(owner=p1, controller=p1)
        game.get_battlefield(p1).add(omni)
        omni.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)
        assert getattr(p1, "_omniscience_active", False)
