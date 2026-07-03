"""Tests for SOS 271 — Forest (Basic Land)."""

from __future__ import annotations

from cards.sos.sos_271.card_impl import Forest
from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype
from test_utils import create_game, set_board_state


class TestForestProperties:
    """Static card data should match the SOS 271 spec."""

    def test_is_land(self) -> None:
        assert isinstance(Forest(owner=None), Land)

    def test_name(self) -> None:
        assert Forest(owner=None).name == "Forest"

    def test_has_basic_supertype(self) -> None:
        card = Forest(owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_forest_subtype(self) -> None:
        card = Forest(owner=None)
        assert "Forest" in card.subtypes

    def test_no_mana_cost(self) -> None:
        card = Forest(owner=None)
        # Basic lands have no mana cost (empty string or None-equivalent)
        cost_str = str(card.mana_cost) if card.mana_cost else ""
        assert cost_str == "" or cost_str == "{0}" or card.mana_cost is None or card.mana_cost.cmc() == 0


class TestForestManaAbility:
    """Forest should have a mana ability that taps for {G}."""

    def test_has_one_mana_ability(self) -> None:
        card = Forest(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 1

    def test_mana_ability_is_mana_ability_instance(self) -> None:
        card = Forest(owner=None)
        abilities = card.get_mana_abilities()
        assert isinstance(abilities[0], ManaAbility)

    def test_mana_ability_description_mentions_green(self) -> None:
        card = Forest(owner=None)
        abilities = card.get_mana_abilities()
        desc = abilities[0].description
        assert "{G}" in desc or "green" in desc.lower()

    def test_tapping_adds_green_mana(self) -> None:
        """Activating the mana ability should add {G} to controller's pool."""
        game = create_game()
        p1 = game.players[0]
        card = Forest(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[0]
        # Activate: pay cost (tap) then produce mana
        cost_paid = ability.cost(game, card)
        assert cost_paid is True
        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.GREEN) >= 1

    def test_tapping_taps_the_land(self) -> None:
        """After activation, the Forest should be tapped."""
        game = create_game()
        p1 = game.players[0]
        card = Forest(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[0]
        ability.cost(game, card)

        assert card.is_tapped is True

    def test_cannot_activate_when_already_tapped(self) -> None:
        """A tapped Forest cannot activate its mana ability again."""
        game = create_game()
        p1 = game.players[0]
        card = Forest(owner=p1, controller=p1)
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])

        abilities = card.get_mana_abilities()
        ability = abilities[0]
        cost_paid = ability.cost(game, card)
        assert cost_paid is False
