"""Tests for SOS 31 — Shattered Acolyte.

A 2/2 Dwarf Warlock for {1}{W} with Lifelink.
Activated ability: {1}, Sacrifice this creature: Destroy target artifact or enchantment.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_31.card_impl import ShatteredAcolyte
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestShatteredAcolyteProperties:
    """Static card data should match the SOS 31 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ShatteredAcolyte(owner=None), Creature)

    def test_name(self) -> None:
        assert ShatteredAcolyte(owner=None).name == "Shattered Acolyte"

    def test_mana_cost(self) -> None:
        assert ShatteredAcolyte(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = ShatteredAcolyte(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_lifelink(self) -> None:
        assert Keyword.LIFELINK in ShatteredAcolyte(owner=None).keywords


class TestShatteredAcolyteActivatedAbility:
    """Sacrifice ability destroys target artifact or enchantment."""

    def test_ability_requires_sacrifice(self) -> None:
        """After activation, the creature should no longer be on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        acolyte = ShatteredAcolyte(owner=p1, controller=p1)
        acolyte.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(acolyte)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})

        # Create a target artifact
        artifact = Creature(name="Sol Ring", base_power=0, base_toughness=0)
        artifact.card_types = {CardType.ARTIFACT}
        artifact.zone = Zone.BATTLEFIELD
        p2 = game.players[1]
        game.get_battlefield(p2).add(artifact)

        # Activate the ability targeting the artifact
        acolyte.activate_ability(game, 0, targets=[artifact])

        # Acolyte should be sacrificed (not on battlefield)
        assert acolyte not in game.get_battlefield(p1)

    def test_ability_destroys_target_artifact(self) -> None:
        """The targeted artifact should be destroyed."""
        game = create_game()
        p1 = game.players[0]
        acolyte = ShatteredAcolyte(owner=p1, controller=p1)
        acolyte.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(acolyte)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})

        p2 = game.players[1]
        artifact = Creature(name="Sol Ring", base_power=0, base_toughness=0)
        artifact.card_types = {CardType.ARTIFACT}
        artifact.zone = Zone.BATTLEFIELD
        artifact.owner = p2
        game.get_battlefield(p2).add(artifact)

        acolyte.activate_ability(game, 0, targets=[artifact])

        assert artifact not in game.get_battlefield(p2)

    def test_ability_destroys_target_enchantment(self) -> None:
        """The targeted enchantment should be destroyed."""
        game = create_game()
        p1 = game.players[0]
        acolyte = ShatteredAcolyte(owner=p1, controller=p1)
        acolyte.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(acolyte)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})

        p2 = game.players[1]
        enchantment = Creature(name="Pacifism", base_power=0, base_toughness=0)
        enchantment.card_types = {CardType.ENCHANTMENT}
        enchantment.zone = Zone.BATTLEFIELD
        enchantment.owner = p2
        game.get_battlefield(p2).add(enchantment)

        acolyte.activate_ability(game, 0, targets=[enchantment])

        assert enchantment not in game.get_battlefield(p2)

    def test_ability_cannot_target_creature(self) -> None:
        """A vanilla creature should not be a legal target."""
        game = create_game()
        p1 = game.players[0]
        acolyte = ShatteredAcolyte(owner=p1, controller=p1)
        acolyte.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(acolyte)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})

        p2 = game.players[1]
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.zone = Zone.BATTLEFIELD
        bear.owner = p2
        game.get_battlefield(p2).add(bear)

        # Attempting to target a creature should fail or be rejected
        with pytest.raises((ValueError, IllegalTargetError, Exception)):
            acolyte.activate_ability(game, 0, targets=[bear])
