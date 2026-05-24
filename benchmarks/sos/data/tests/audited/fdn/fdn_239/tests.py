"""Audited tests for FDN 239 — Empyrean Eagle."""

from __future__ import annotations

from card_impl import EmpyreanEagle
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestEmpyreanEagleBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = EmpyreanEagle(owner=None)
        assert card.name == "Empyrean Eagle"

    def test_mana_cost(self) -> None:
        card = EmpyreanEagle(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{U}")

    def test_power_toughness(self) -> None:
        card = EmpyreanEagle(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = EmpyreanEagle(owner=None)
        assert Keyword.FLYING & card.keywords

    def test_subtypes(self) -> None:
        card = EmpyreanEagle(owner=None)
        assert "Bird" in card.subtypes
        assert "Spirit" in card.subtypes


class TestEmpyreanEagleLord:
    """Other creatures you control with flying get +1/+1."""

    def test_buffs_other_flyer(self) -> None:
        game = create_game()
        p1 = game.players[0]
        eagle = EmpyreanEagle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(eagle)
        flyer = Creature(name="Bird", base_power=1, base_toughness=1,
                         keywords=Keyword.FLYING, owner=p1, controller=p1)
        game.get_battlefield(p1).add(flyer)
        eagle.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert flyer.modified_power == 2
        assert flyer.modified_toughness == 2

    def test_does_not_buff_self(self) -> None:
        game = create_game()
        p1 = game.players[0]
        eagle = EmpyreanEagle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(eagle)
        eagle.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert eagle.base_power == 2
        assert eagle.base_toughness == 3

    def test_does_not_buff_non_flyer(self) -> None:
        game = create_game()
        p1 = game.players[0]
        eagle = EmpyreanEagle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(eagle)
        ground = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(ground)
        eagle.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert ground.base_power == 2
        assert ground.base_toughness == 2

