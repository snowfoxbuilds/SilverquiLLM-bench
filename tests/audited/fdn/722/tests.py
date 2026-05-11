"""Audited tests for Unflinching Courage (FDN collector number 722)."""
from __future__ import annotations
import pytest
from card_impl import UnflinchingCourage
from engine.card import Aura, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestUnflinchingCourageBasic:
    def test_is_aura(self) -> None:
        assert isinstance(UnflinchingCourage(name="Unflinching Courage", owner=None), Aura)

@pytest.mark.ability
class TestUnflinchingCourageAbility:
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UnflinchingCourage(name="Unflinching Courage", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 4
    def test_trample(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UnflinchingCourage(name="Unflinching Courage", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE in c.keywords
    def test_lifelink(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UnflinchingCourage(name="Unflinching Courage", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.LIFELINK in c.keywords
