"""Audited tests for FDN 109 — Preposterous Proportions."""

from __future__ import annotations

from card_impl import PreposterousProportions
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestPreposterousProportionsBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = PreposterousProportions(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = PreposterousProportions(owner=None)
        assert card.name == "Preposterous Proportions"

    def test_mana_cost(self) -> None:
        card = PreposterousProportions(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{G}{G}")


class TestPreposterousProportionsResolve:
    """Creatures you control get +10/+10 and vigilance until EOT."""

    def test_creatures_get_plus_10_10(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PreposterousProportions(owner=p1, controller=p1)
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.modified_power == 12  # 2 + 10
        assert c1.modified_toughness == 12  # 2 + 10

    def test_creatures_gain_vigilance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PreposterousProportions(owner=p1, controller=p1)
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.VIGILANCE in c1.keywords

    def test_multiple_creatures_all_buffed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PreposterousProportions(owner=p1, controller=p1)
        c1 = Creature(name="Bear1", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Bear2", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.modified_power == 12
        assert c2.modified_power == 13

    def test_opponent_creatures_not_affected(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = PreposterousProportions(owner=p1, controller=p1)
        opp = Creature(name="Opp", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp.base_power == 3
        assert opp.base_toughness == 3

    def test_no_creatures_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PreposterousProportions(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Should not crash
