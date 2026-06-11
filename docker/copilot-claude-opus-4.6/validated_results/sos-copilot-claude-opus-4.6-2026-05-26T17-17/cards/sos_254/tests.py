"""Tests for SOS 254 — Dreamroot Cascade.

Land:
- Enters tapped unless you control two or more other lands.
- {T}: Add {G} or {U}.
"""

from __future__ import annotations

from cards.sos.sos_254.card_impl import DreamrootCascade
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game


class TestDreamrootCascadeProperties:
    """Static card data should match the SOS 254 spec."""

    def test_name(self) -> None:
        card = DreamrootCascade(owner=None)
        assert card.name == "Dreamroot Cascade"

    def test_is_land(self) -> None:
        card = DreamrootCascade(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = DreamrootCascade(owner=None)
        assert card.mana_cost is None or card.mana_cost == ManaCost.parse("{0}")


class TestDreamrootCascadeManaAbilities:
    """{T}: Add {G} or {U}."""

    def test_has_mana_abilities(self) -> None:
        card = DreamrootCascade(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_green(self) -> None:
        card = DreamrootCascade(owner=None)
        abilities = card.get_mana_abilities()
        all_types = []
        for a in abilities:
            if hasattr(a, "mana_types"):
                all_types.extend(a.mana_types)
            elif hasattr(a, "mana_type"):
                all_types.append(a.mana_type)
        assert ManaType.GREEN in all_types

    def test_can_produce_blue(self) -> None:
        card = DreamrootCascade(owner=None)
        abilities = card.get_mana_abilities()
        all_types = []
        for a in abilities:
            if hasattr(a, "mana_types"):
                all_types.extend(a.mana_types)
            elif hasattr(a, "mana_type"):
                all_types.append(a.mana_type)
        assert ManaType.BLUE in all_types


class TestDreamrootCascadeEntersTapped:
    """Enters tapped unless you control two or more other lands."""

    def test_enters_tapped_with_zero_other_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DreamrootCascade(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_with_one_other_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        other_land = Land(owner=p1, controller=p1, name="Island")
        game.get_battlefield(p1).add(other_land)
        card = DreamrootCascade(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_untapped_with_two_other_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land1 = Land(owner=p1, controller=p1, name="Forest")
        land2 = Land(owner=p1, controller=p1, name="Island")
        game.get_battlefield(p1).add(land1)
        game.get_battlefield(p1).add(land2)
        card = DreamrootCascade(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is False

    def test_enters_untapped_with_many_other_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        for i in range(4):
            land = Land(owner=p1, controller=p1, name=f"Land{i}")
            game.get_battlefield(p1).add(land)
        card = DreamrootCascade(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is False
