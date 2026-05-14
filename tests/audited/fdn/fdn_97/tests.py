"""Audited tests for FDN 97 — Twinflame Tyrant."""

from __future__ import annotations

from card_impl import TwinflameTyrant
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestTwinflameTyrantBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = TwinflameTyrant(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TwinflameTyrant(owner=None)
        assert card.name == "Twinflame Tyrant"

    def test_mana_cost(self) -> None:
        card = TwinflameTyrant(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{R}")

    def test_power_toughness(self) -> None:
        card = TwinflameTyrant(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = TwinflameTyrant(owner=None)
        kw = getattr(card, "keywords", Keyword(0)) or Keyword(0)
        assert kw & Keyword.FLYING

    def test_subtypes(self) -> None:
        card = TwinflameTyrant(owner=None)
        assert "Dragon" in card.subtypes


class TestTwinflameTyrantDamageDoubling:
    """Damage doubling continuous effect."""

    def test_sets_double_damage_flag_on_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TwinflameTyrant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.apply_continuous_effect(game)
        # Apply effects
        for eff in game.effect_manager.get_all():
            eff.apply(game)
        assert getattr(p1, "_double_damage_to_opponents", False) is True

    def test_cleanup_on_leaving_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TwinflameTyrant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        p1._double_damage_to_opponents = True
        card.unregister_triggers(game)
        assert not hasattr(p1, "_double_damage_to_opponents")
