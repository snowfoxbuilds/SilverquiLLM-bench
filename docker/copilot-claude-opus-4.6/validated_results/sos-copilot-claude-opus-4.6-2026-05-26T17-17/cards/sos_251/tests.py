"""Tests for SOS 251 — Potioner's Trove.

An artifact with two tap abilities:
1. {T}: Add one mana of any color.
2. {T}: You gain 2 life. Activate only if you've cast an instant or sorcery spell this turn.
"""

from __future__ import annotations

from cards.sos.sos_251.card_impl import PotionersTrove
from engine.card import Artifact, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game


class TestPotionersTroveProperties:
    """Static card data should match the SOS 251 spec."""

    def test_name(self) -> None:
        card = PotionersTrove(owner=None)
        assert card.name == "Potioner's Trove"

    def test_mana_cost(self) -> None:
        card = PotionersTrove(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}")

    def test_is_artifact(self) -> None:
        card = PotionersTrove(owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types

    def test_no_power_toughness(self) -> None:
        card = PotionersTrove(owner=None)
        assert not hasattr(card, "base_power") or card.base_power is None


class TestPotionersTroveManaAbility:
    """First ability: {T}: Add one mana of any color."""

    def test_has_mana_ability(self) -> None:
        card = PotionersTrove(owner=None)
        mana_abilities = card.get_mana_abilities()
        assert len(mana_abilities) >= 1

    def test_mana_ability_is_mana_ability_type(self) -> None:
        card = PotionersTrove(owner=None)
        mana_abilities = card.get_mana_abilities()
        assert isinstance(mana_abilities[0], ManaAbility)

    def test_mana_ability_produces_any_color(self) -> None:
        """The mana ability should be able to produce any color of mana."""
        game = create_game()
        p1 = game.players[0]
        card = PotionersTrove(owner=p1, controller=p1)
        card.is_tapped = False
        mana_abilities = card.get_mana_abilities()
        # The ability should indicate it can produce any color
        ability = mana_abilities[0]
        # Check that all five colors are available (or a wildcard)
        assert len(ability.mana_types) >= 5 or hasattr(ability, "any_color") and ability.any_color

    def test_tapping_for_mana_taps_artifact(self) -> None:
        """After activating the mana ability, the artifact should be tapped."""
        game = create_game()
        p1 = game.players[0]
        card = PotionersTrove(owner=p1, controller=p1)
        card.is_tapped = False
        mana_abilities = card.get_mana_abilities()
        ability = mana_abilities[0]
        ability.activate(game, card, p1)
        assert card.is_tapped is True


class TestPotionersTroveLifeAbility:
    """{T}: You gain 2 life. Activate only if you've cast an instant or sorcery this turn."""

    def test_has_activated_ability(self) -> None:
        card = PotionersTrove(owner=None)
        abilities = card.get_activated_abilities()
        # Should have at least the life-gain ability
        assert len(abilities) >= 1

    def test_life_gain_ability_gives_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PotionersTrove(owner=p1, controller=p1)
        card.is_tapped = False
        # Mark that the player has cast an instant or sorcery this turn
        p1.cast_instant_or_sorcery_this_turn = True
        abilities = card.get_activated_abilities()
        life_ability = abilities[0]
        starting_life = p1.life
        life_ability.activate(game, card, p1)
        assert p1.life == starting_life + 2

    def test_life_ability_cannot_activate_without_instant_or_sorcery(self) -> None:
        """The restriction should prevent activation if no instant/sorcery cast."""
        game = create_game()
        p1 = game.players[0]
        card = PotionersTrove(owner=p1, controller=p1)
        card.is_tapped = False
        p1.cast_instant_or_sorcery_this_turn = False
        abilities = card.get_activated_abilities()
        life_ability = abilities[0]
        # Should not be activatable
        assert life_ability.can_activate(game, card, p1) is False

    def test_life_ability_can_activate_after_instant_cast(self) -> None:
        """After casting an instant this turn, the ability should be available."""
        game = create_game()
        p1 = game.players[0]
        card = PotionersTrove(owner=p1, controller=p1)
        card.is_tapped = False
        p1.cast_instant_or_sorcery_this_turn = True
        abilities = card.get_activated_abilities()
        life_ability = abilities[0]
        assert life_ability.can_activate(game, card, p1) is True
