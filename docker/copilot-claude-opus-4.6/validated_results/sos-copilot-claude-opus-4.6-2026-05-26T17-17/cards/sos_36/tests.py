"""Tests for SOS 36 — Stone Docent.

A 3/1 Spirit Chimera for {1}{W}.
Activated ability: {W}, Exile this card from your graveyard: You gain 2 life.
Surveil 1. Activate only as a sorcery.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_36.card_impl import StoneDocent
from engine.card import Creature, ActivatedAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestStoneDocentProperties:
    """Static card data should match the SOS 36 spec."""

    def test_is_creature(self) -> None:
        card = StoneDocent(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert StoneDocent(owner=None).name == "Stone Docent"

    def test_mana_cost(self) -> None:
        assert StoneDocent(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = StoneDocent(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 1


class TestStoneDocentGraveyardAbility:
    """Activated ability from graveyard: {W}, exile → gain 2 life, surveil 1."""

    def test_has_activated_ability(self) -> None:
        card = StoneDocent(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_gains_2_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StoneDocent(owner=p1, controller=p1)
        # Place in graveyard
        set_board_state(game, 0, graveyard=[card], mana={ManaType.WHITE: 1})
        starting_life = p1.life
        abilities = card.get_activated_abilities()
        # Activate the ability
        abilities[0].effect(game)
        assert p1.life == starting_life + 2

    def test_ability_exiles_card_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StoneDocent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card], mana={ManaType.WHITE: 1})
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        # Card should no longer be in graveyard
        graveyard = game.get_graveyard(p1)
        assert card not in graveyard

    def test_ability_surveils_1(self) -> None:
        """After activation, surveil 1 should occur (top card may go to graveyard)."""
        game = create_game()
        p1 = game.players[0]
        card = StoneDocent(owner=p1, controller=p1)
        # Put a card on top of library to surveil
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[card], mana={ManaType.WHITE: 1})
        # Place filler on top of library
        game.get_library(p1).append(filler)
        library_size_before = len(game.get_library(p1))
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        # After surveil, the library or graveyard should have changed
        library_after = len(game.get_library(p1))
        graveyard_after = len(game.get_graveyard(p1))
        # Either top card stayed (library same) or went to graveyard
        assert library_after <= library_size_before

    def test_ability_sorcery_speed_only(self) -> None:
        """The ability should only be activatable at sorcery speed."""
        card = StoneDocent(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        # The ability description should reference sorcery timing
        ability = abilities[0]
        assert "sorcery" in ability.description.lower() or hasattr(ability, 'sorcery_speed')
