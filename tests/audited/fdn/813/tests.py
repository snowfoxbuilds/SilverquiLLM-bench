"""Audited tests for Arrest (FDN — synthetic dir 813)."""
from __future__ import annotations
import pytest
from card_impl import Arrest
from engine.card import Aura, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestArrestBasic:
    def test_is_aura(self) -> None:
        assert isinstance(Arrest(name="Arrest", owner=None), Aura)

@pytest.mark.ability
class TestArrestAbility:
    def test_cant_attack(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = Arrest(name="Arrest", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(c, "_cant_attack", False)
    def test_cant_block(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = Arrest(name="Arrest", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert getattr(c, "_cant_block", False)
    def test_attach_sets_target(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = Arrest(name="Arrest", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        assert a.attached_to is c
