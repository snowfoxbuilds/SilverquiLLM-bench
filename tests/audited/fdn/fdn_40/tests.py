"""Audited tests for FDN 40 — High Fae Trickster."""

from __future__ import annotations

from card_impl import HighFaeTrickster
from engine.card import Creature
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


class TestHighFaeTricksterBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert card.name == "High Fae Trickster"

    def test_mana_cost(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_has_flash(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_flying(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_faerie_wizard_subtypes(self) -> None:
        card = HighFaeTrickster(owner=None)
        assert "Faerie" in card.subtypes
        assert "Wizard" in card.subtypes


class TestHighFaeTricksterFlashGrant:
    """You may cast spells as though they had flash."""

    def test_register_sets_flash_grant_on_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HighFaeTrickster(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert getattr(p1, "can_cast_as_flash", False) is True

    def test_unregister_removes_flash_grant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HighFaeTrickster(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        card.unregister_triggers(game)
        assert getattr(p1, "can_cast_as_flash", False) is False

    def test_flash_grant_not_applied_when_off_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HighFaeTrickster(owner=p1, controller=p1)
        # Register but don't put on battlefield
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert getattr(p1, "can_cast_as_flash", False) is False
