"""Audited tests for Elementalist Adept (FDN collector number 36) — flash."""

from __future__ import annotations

import pytest

from card_impl import ElementalistAdept

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestElementalistAdeptProperties:
    def test_is_creature(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert card.toughness == 1

    def test_has_human_subtype(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert "Human" in card.subtypes

    def test_has_wizard_subtype(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert "Wizard" in card.subtypes


@pytest.mark.ability
class TestElementalistAdeptKeywords:
    def test_has_flash(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert Keyword.FLASH in card.keywords

    def test_only_flash(self) -> None:
        card = ElementalistAdept(name="Elementalist Adept", owner=None)
        assert card.keywords == Keyword.FLASH


@pytest.mark.behavior
class TestElementalistAdeptBehavior:
    """Flash behavior: can be cast at instant speed (during opponent's turn)."""

    def test_flash_creature_can_be_cast_during_combat(self) -> None:
        """A flash creature can be cast outside main phase timing."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType, Phase, Step

        game = create_game()
        card = ElementalistAdept(name="Elementalist Adept", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.BLUE: 3})
        # Flash allows casting during combat
        game.phase = Phase.COMBAT
        game.step = Step.BEGIN_COMBAT
        game.active_player_index = 0
        game.priority_player_index = 0
        cast_spell(game, 0, "Elementalist Adept")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()
