"""Audited tests for FDN 254 — Heraldic Banner."""

from __future__ import annotations

from card_impl import HeraldicBanner
from engine.card import Artifact, ManaAbility
from engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game


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

    def test_chosen_color_starts_none(self) -> None:
        """chosen_color should default to None before a color is chosen."""
        card = HeraldicBanner(owner=None)
        assert card.chosen_color is None


class TestHeraldicBannerManaAbility:
    """{T}: Add one mana of the chosen color."""

    def test_has_exactly_one_mana_ability(self) -> None:
        card = HeraldicBanner(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1

    def test_tap_for_mana_adds_exactly_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        banner = HeraldicBanner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(banner)

        abilities = banner.get_mana_abilities()
        mana_before = p1.mana_pool.total()
        assert abilities[0].cost(game, banner)
        abilities[0].mana_produced(game)
        assert p1.mana_pool.total() == mana_before + 1

    def test_tap_for_mana_taps_the_artifact(self) -> None:
        """Activating the mana ability should tap the banner."""
        game = create_game()
        p1 = game.players[0]
        banner = HeraldicBanner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(banner)

        abilities = banner.get_mana_abilities()
        assert not getattr(banner, "is_tapped", False)
        abilities[0].cost(game, banner)
        assert banner.is_tapped is True

    def test_cannot_tap_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        banner = HeraldicBanner(owner=p1, controller=p1)
        banner.is_tapped = True
        game.get_battlefield(p1).add(banner)

        abilities = banner.get_mana_abilities()
        assert not abilities[0].cost(game, banner)

    def test_mana_ability_description_mentions_chosen_color(self) -> None:
        """The mana ability description should reference the chosen color."""
        card = HeraldicBanner(owner=None)
        abilities = card.get_mana_abilities()
        assert "chosen color" in abilities[0].description.lower()

    def test_rules_text_mentions_lord_effect(self) -> None:
        """Rules text should mention the +1/+0 buff to creatures of chosen color."""
        card = HeraldicBanner(owner=None)
        assert "+1/+0" in card.rules_text

