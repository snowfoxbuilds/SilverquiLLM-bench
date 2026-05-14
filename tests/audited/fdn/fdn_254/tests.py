"""Audited tests for FDN 254 — Heraldic Banner."""

from __future__ import annotations

from card_impl import HeraldicBanner
from engine.card import Artifact, ManaAbility
from engine.types import ManaCost, ManaType
from tests.test_utils import create_game


class TestHeraldicBannerBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = HeraldicBanner(owner=None)
        assert card.name == "Heraldic Banner"

    def test_mana_cost(self) -> None:
        card = HeraldicBanner(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}")

    def test_is_artifact(self) -> None:
        card = HeraldicBanner(owner=None)
        assert isinstance(card, Artifact)

    def test_has_chosen_color_attribute(self) -> None:
        card = HeraldicBanner(owner=None)
        assert hasattr(card, "chosen_color")


class TestHeraldicBannerManaAbility:
    """{T}: Add one mana of the chosen color."""

    def test_has_mana_ability(self) -> None:
        card = HeraldicBanner(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_tap_for_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        banner = HeraldicBanner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(banner)

        abilities = banner.get_mana_abilities()
        mana_before = p1.mana_pool.total()
        assert abilities[0].cost(game, banner)
        abilities[0].mana_produced(game)
        assert p1.mana_pool.total() == mana_before + 1

    def test_cannot_tap_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        banner = HeraldicBanner(owner=p1, controller=p1)
        banner.is_tapped = True
        game.get_battlefield(p1).add(banner)

        abilities = banner.get_mana_abilities()
        assert not abilities[0].cost(game, banner)

