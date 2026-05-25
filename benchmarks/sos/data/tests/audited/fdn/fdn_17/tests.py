"""Audited tests for FDN 17 — Herald of Eternal Dawn."""

from __future__ import annotations

from card_impl import HeraldOfEternalDawn
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game


class TestHeraldOfEternalDawnBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert card.name == "Herald of Eternal Dawn"

    def test_mana_cost(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{W}{W}{W}")

    def test_power_toughness(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_has_flash(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_flying(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_angel_subtype(self) -> None:
        card = HeraldOfEternalDawn(owner=None)
        assert "Angel" in card.subtypes


class TestHeraldCantLoseEffect:
    """You can't lose the game and opponents can't win the game."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        herald = HeraldOfEternalDawn(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(herald)
        herald.register_triggers(game)
        game.effect_manager.apply_all(game)
        return game, herald, p1, p2

    def test_controller_gets_cant_lose(self) -> None:
        game, herald, p1, p2 = self._setup()
        assert getattr(p1, "cant_lose", False) is True

    def test_opponent_gets_cant_win(self) -> None:
        game, herald, p1, p2 = self._setup()
        assert getattr(p2, "cant_win", False) is True

    def test_effect_registered_as_continuous(self) -> None:
        game, herald, p1, p2 = self._setup()
        effects = game.effect_manager.get_effects_by_source(herald)
        assert len(effects) >= 1
