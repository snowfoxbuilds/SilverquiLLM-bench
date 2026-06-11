"""Tests for SOS 257 — Great Hall of the Biblioplex.

Land with:
- {T}: Add {C}.
- {T}, Pay 1 life: Add one mana of any color. Spend only on instant/sorcery.
- {5}: Becomes a 2/4 Wizard creature with pump trigger. Still a land.
"""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game


class TestGreatHallProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_has_land_card_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types


class TestGreatHallColorlessMana:
    """{T}: Add {C}."""

    def test_has_colorless_mana_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        colorless_found = any(
            ManaType.COLORLESS in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert colorless_found is True


class TestGreatHallAnyColorMana:
    """{T}, Pay 1 life: Add one mana of any color (instant/sorcery only)."""

    def test_has_any_color_mana_ability(self) -> None:
        """Should have a mana ability that produces any color."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        any_color_found = any(
            getattr(a, 'any_color', False) for a in abilities
        )
        assert any_color_found is True

    def test_any_color_ability_costs_life(self) -> None:
        """Activating the any-color ability should cost 1 life."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = False
        life_before = p1.life
        # Find the any-color ability
        abilities = card.get_mana_abilities()
        any_color_ability = next(
            (a for a in abilities if getattr(a, 'any_color', False)), None
        )
        assert any_color_ability is not None
        any_color_ability.activate(game, card, p1)
        assert p1.life == life_before - 1


class TestGreatHallAnimation:
    """{5}: Becomes 2/4 Wizard creature, still a land."""

    def test_has_animation_activated_ability(self) -> None:
        """Should have an activated ability for the {5} animation."""
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_becomes_creature_after_activation(self) -> None:
        """After paying {5}, should become a creature."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities()
        # Activate the animation ability
        animation = abilities[0]
        animation.activate(game, card, p1)
        assert CardType.CREATURE in card.card_types

    def test_still_a_land_after_animation(self) -> None:
        """After animation, should still be a land."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities()
        animation = abilities[0]
        animation.activate(game, card, p1)
        assert CardType.LAND in card.card_types

    def test_has_2_4_stats_after_animation(self) -> None:
        """Should be a 2/4 after activation."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities()
        animation = abilities[0]
        animation.activate(game, card, p1)
        assert card.base_power == 2
        assert card.base_toughness == 4

    def test_does_not_animate_if_already_creature(self) -> None:
        """'If this land isn't a creature' — should not re-animate."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities()
        animation = abilities[0]
        # Animate once
        animation.activate(game, card, p1)
        # Animate again — should be no-op (already a creature)
        animation.activate(game, card, p1)
        assert card.base_power == 2
        assert card.base_toughness == 4
