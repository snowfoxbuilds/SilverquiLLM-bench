"""Audited tests for FDN 140 — Day of Judgment."""

from __future__ import annotations

from card_impl import DayOfJudgment
from engine.card import CardImpl, Creature, Enchantment, Sorcery
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDayOfJudgmentBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = DayOfJudgment(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = DayOfJudgment(owner=None)
        assert card.name == "Day of Judgment"

    def test_mana_cost(self) -> None:
        card = DayOfJudgment(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{W}")


class TestDayOfJudgmentResolve:
    """Destroy all creatures."""

    def test_destroys_own_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        doj = DayOfJudgment(owner=p1, controller=p1)
        doj.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        creature_names = [getattr(c, "name", "") for c in bf if CardType.CREATURE in getattr(c, "card_types", set())]
        assert "Bear" not in creature_names

    def test_destroys_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(c1)
        doj = DayOfJudgment(owner=p1, controller=p1)
        doj.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        creature_names = [getattr(c, "name", "") for c in bf if CardType.CREATURE in getattr(c, "card_types", set())]
        assert "Bear" not in creature_names

    def test_destroys_all_creatures_both_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p2).add(c2)
        doj = DayOfJudgment(owner=p1, controller=p1)
        doj.on_resolve(game)
        all_bf = list(game.get_battlefield(p1).get_all()) + list(game.get_battlefield(p2).get_all())
        creatures = [c for c in all_bf if CardType.CREATURE in getattr(c, "card_types", set())]
        assert len(creatures) == 0

    def test_does_not_destroy_noncreatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ench = Enchantment(name="Test Enchantment", owner=p1, controller=p1)
        game.get_battlefield(p1).add(ench)
        doj = DayOfJudgment(owner=p1, controller=p1)
        doj.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        assert any(getattr(c, "name", "") == "Test Enchantment" for c in bf)

    def test_empty_battlefield_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        doj = DayOfJudgment(owner=p1, controller=p1)
        doj.on_resolve(game)  # Should not raise
