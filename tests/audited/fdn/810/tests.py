"""Audited tests for Holy Strength (FDN — synthetic dir 810)."""
from __future__ import annotations
import pytest
from card_impl import HolyStrength
from engine.card import Aura, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestHolyStrengthBasic:
    def test_is_aura(self) -> None:
        card = HolyStrength(name="Holy Strength", owner=None)
        assert isinstance(card, Aura)
        assert card.is_aura is True
    def test_has_aura_subtype(self) -> None:
        card = HolyStrength(name="Holy Strength", owner=None)
        assert "Aura" in card.subtypes

@pytest.mark.ability
class TestHolyStrengthAbility:
    def test_grants_plus1_power(self) -> None:
        """Holy Strength gives exactly +1/+2."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = HolyStrength(name="Holy Strength", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 3
    def test_grants_plus2_toughness(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = HolyStrength(name="Holy Strength", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness == 4
    def test_attaches_to_target(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = HolyStrength(name="Holy Strength", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        assert a.attached_to is c

@pytest.mark.interaction
class TestHolyStrengthInteraction:
    def test_stacking_two_auras(self) -> None:
        """Two Holy Strengths on the same creature stack additively."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a1 = HolyStrength(name="Holy Strength", owner=game.players[0])
        a2 = HolyStrength(name="Holy Strength", owner=game.players[0])
        a1.controller = game.players[0]
        a2.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a1, a2])
        a1.chosen_targets = [c]; a1.on_resolve(game)
        a2.chosen_targets = [c]; a2.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 4  # 2 + 1 + 1
        assert c.base_toughness == 6  # 2 + 2 + 2
