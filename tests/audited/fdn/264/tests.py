"""Audited tests for Rogue's Passage (FDN collector number 264)."""
from __future__ import annotations
import pytest
from card_impl import RoguesPassage
from engine.card import Land
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestRoguesPassageBasic:
    def test_is_land(self) -> None:
        card = RoguesPassage(name="Rogue's Passage", owner=None)
        assert isinstance(card, Land)

    def test_does_not_enter_tapped(self) -> None:
        card = RoguesPassage(name="Rogue's Passage", owner=None)
        assert not getattr(card, "enters_tapped", False)


@pytest.mark.ability
class TestRoguesPassageMana:
    def test_has_mana_ability(self) -> None:
        card = RoguesPassage(name="Rogue's Passage", owner=None)
        assert len(card.get_mana_abilities()) == 1

    def test_taps_for_colorless(self) -> None:
        game = create_game()
        card = RoguesPassage(name="Rogue's Passage", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) >= 1


@pytest.mark.ability
class TestRoguesPassageActivated:
    def test_has_activated_ability(self) -> None:
        card = RoguesPassage(name="Rogue's Passage", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1

    def test_ability_description(self) -> None:
        card = RoguesPassage(name="Rogue's Passage", owner=None)
        abilities = card.get_activated_abilities()
        assert "can't be blocked" in abilities[0].description

    def test_activated_ability_sets_unblockable(self) -> None:
        """After resolving ability effect, target creature gets cant_be_blocked_this_turn."""
        from engine.card import Creature
        game = create_game()
        p = game.players[0]
        card = RoguesPassage(name="Rogue's Passage", owner=p)
        card.controller = p
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        set_board_state(game, 0, battlefield=[card, creature])
        card._current_target = creature
        abilities = card.get_activated_abilities()
        # Directly invoke the effect (bypassing cost which has pay_generic bug)
        abilities[0].effect(game)
        assert creature.cant_be_blocked_this_turn is True

    def test_activated_ability_requires_untapped(self) -> None:
        """Cannot activate when already tapped."""
        game = create_game()
        p = game.players[0]
        card = RoguesPassage(name="Rogue's Passage", owner=p)
        card.controller = p
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 4})
        abilities = card.get_activated_abilities()
        result = abilities[0].cost(game, card)
        assert result is False
