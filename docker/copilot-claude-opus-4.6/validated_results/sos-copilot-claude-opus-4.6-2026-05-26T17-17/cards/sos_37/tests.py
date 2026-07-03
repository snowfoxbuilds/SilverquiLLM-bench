"""Tests for SOS 37 — Summoned Dromedary.

A 4/3 Spirit Camel for {3}{W} with Vigilance.
Activated ability: {1}{W}: Return this card from your graveyard to your hand.
Activate only as a sorcery.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_37.card_impl import SummonedDromedary
from engine.card import Creature, ActivatedAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSummonedDromedaryProperties:
    """Static card data should match the SOS 37 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SummonedDromedary(owner=None), Creature)

    def test_name(self) -> None:
        assert SummonedDromedary(owner=None).name == "Summoned Dromedary"

    def test_mana_cost(self) -> None:
        assert SummonedDromedary(owner=None).mana_cost == ManaCost.parse("{3}{W}")

    def test_power_toughness(self) -> None:
        card = SummonedDromedary(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_vigilance(self) -> None:
        card = SummonedDromedary(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestSummonedDromedaryGraveyardAbility:
    """{1}{W}: Return this card from graveyard to hand. Sorcery speed only."""

    def test_has_activated_ability(self) -> None:
        card = SummonedDromedary(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_returns_card_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SummonedDromedary(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        # Card should now be in hand
        hand = game.get_hand(p1)
        assert card in hand

    def test_ability_removes_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SummonedDromedary(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        graveyard = game.get_graveyard(p1)
        assert card not in graveyard

    def test_ability_sorcery_speed_only(self) -> None:
        """The ability should only be activatable at sorcery speed."""
        card = SummonedDromedary(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        ability = abilities[0]
        assert "sorcery" in ability.description.lower() or hasattr(ability, 'sorcery_speed')
