"""Audited tests for Goblin Firebomb (FDN collector number 562)."""
from __future__ import annotations
import pytest
from card_impl import GoblinFirebomb
from engine.card import Artifact, Creature
from engine.types import CardType, Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGoblinFirebombBasic:
    def test_is_artifact(self) -> None:
        card = GoblinFirebomb(name="Goblin Firebomb", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = GoblinFirebomb(name="Goblin Firebomb", owner=None)
        assert card.name == "Goblin Firebomb"
    def test_has_flash(self) -> None:
        card = GoblinFirebomb(name="Goblin Firebomb", owner=None)
        assert Keyword.FLASH in card.keywords
    def test_has_activated_ability(self) -> None:
        card = GoblinFirebomb(name="Goblin Firebomb", owner=None)
        assert len(card.get_activated_abilities()) >= 1

@pytest.mark.ability
class TestGoblinFirebombAbility:
    def test_activation_destroys_target_permanent(self) -> None:
        """Activated ability should destroy the targeted permanent."""
        game = create_game()
        bomb = GoblinFirebomb(name="Goblin Firebomb", owner=game.players[0])
        bomb.controller = game.players[0]
        target_c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[1])
        set_board_state(game, 0, battlefield=[bomb])
        set_board_state(game, 1, battlefield=[target_c])
        bomb._resolve_target = target_c
        abilities = bomb.get_activated_abilities()
        cost_paid = abilities[0].cost(game, bomb)
        assert cost_paid
        abilities[0].effect(game)
        bf = game.get_battlefield(game.players[1])
        assert not bf.contains(target_c), "Target should be destroyed"

    def test_cannot_activate_when_tapped(self) -> None:
        game = create_game()
        bomb = GoblinFirebomb(name="Goblin Firebomb", owner=game.players[0])
        bomb.is_tapped = True
        abilities = bomb.get_activated_abilities()
        assert not abilities[0].cost(game, bomb)
