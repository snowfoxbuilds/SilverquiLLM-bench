"""Tests for SOS 259 — Petrified Hamlet.

Land with:
- When enters, choose a land card name.
- Activated abilities of sources with chosen name can't be activated (unless mana abilities).
- Lands with the chosen name have '{T}: Add {C}'.
- {T}: Add {C}.
"""

from __future__ import annotations

from cards.sos.sos_259.card_impl import PetrifiedHamlet
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game


class TestPetrifiedHamletProperties:
    """Static card data should match the SOS 259 spec."""

    def test_is_land(self) -> None:
        card = PetrifiedHamlet(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = PetrifiedHamlet(owner=None)
        assert card.name == "Petrified Hamlet"

    def test_has_land_card_type(self) -> None:
        card = PetrifiedHamlet(owner=None)
        assert CardType.LAND in card.card_types


class TestPetrifiedHamletManaAbility:
    """{T}: Add {C}."""

    def test_has_colorless_mana_ability(self) -> None:
        card = PetrifiedHamlet(owner=None)
        abilities = card.get_mana_abilities()
        colorless_found = any(
            ManaType.COLORLESS in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert colorless_found is True


class TestPetrifiedHamletEntersTrigger:
    """When this land enters, choose a land card name."""

    def test_has_enter_battlefield_trigger(self) -> None:
        """Should have an ETB trigger that asks for a name choice."""
        game = create_game()
        p1 = game.players[0]
        card = PetrifiedHamlet(owner=p1, controller=p1)
        # The card should have a method or trigger for ETB
        assert hasattr(card, 'enter_battlefield') or hasattr(card, 'on_enter_battlefield')

    def test_stores_chosen_name(self) -> None:
        """After ETB, the card should store the chosen land name."""
        game = create_game()
        p1 = game.players[0]
        card = PetrifiedHamlet(owner=p1, controller=p1)
        card.enter_battlefield(game, choice="Gaea's Cradle")
        assert card.chosen_name == "Gaea's Cradle"


class TestPetrifiedHamletLockdown:
    """Non-mana activated abilities of sources with chosen name can't be activated."""

    def test_blocks_non_mana_abilities_of_named_land(self) -> None:
        """A land with the chosen name should not be able to activate non-mana abilities."""
        game = create_game()
        p1 = game.players[0]
        hamlet = PetrifiedHamlet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hamlet)
        hamlet.enter_battlefield(game, choice="Maze of Ith")

        # Create a fake land named "Maze of Ith" with an activated ability
        from engine.card import Land as LandBase
        target_land = LandBase(name="Maze of Ith", owner=p1, controller=p1)
        game.get_battlefield(p1).add(target_land)

        # The ability restriction check should prevent activation
        assert hamlet.blocks_ability(game, target_land, mana_ability=False) is True

    def test_does_not_block_mana_abilities_of_named_land(self) -> None:
        """Mana abilities should still work on lands with the chosen name."""
        game = create_game()
        p1 = game.players[0]
        hamlet = PetrifiedHamlet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hamlet)
        hamlet.enter_battlefield(game, choice="Maze of Ith")

        from engine.card import Land as LandBase
        target_land = LandBase(name="Maze of Ith", owner=p1, controller=p1)
        game.get_battlefield(p1).add(target_land)

        assert hamlet.blocks_ability(game, target_land, mana_ability=True) is False


class TestPetrifiedHamletGrantsColorless:
    """Lands with the chosen name have '{T}: Add {C}'."""

    def test_named_lands_gain_colorless_tap_ability(self) -> None:
        """Lands matching the chosen name should gain a {C} mana ability."""
        game = create_game()
        p1 = game.players[0]
        hamlet = PetrifiedHamlet(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hamlet)
        hamlet.enter_battlefield(game, choice="Gaea's Cradle")

        from engine.card import Land as LandBase
        target_land = LandBase(name="Gaea's Cradle", owner=p1, controller=p1)
        game.get_battlefield(p1).add(target_land)

        # After hamlet's effect is active, target_land should have {C} ability
        abilities = hamlet.get_granted_mana_abilities(game, target_land)
        assert len(abilities) >= 1
        colorless_found = any(
            ManaType.COLORLESS in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert colorless_found is True
