"""Audited tests for FDN 230 — Overrun."""

from __future__ import annotations

from card_impl import Overrun
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game


class TestOverrunBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = Overrun(owner=None)
        assert card.name == "Overrun"

    def test_mana_cost(self) -> None:
        card = Overrun(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}{G}{G}")

    def test_is_sorcery(self) -> None:
        card = Overrun(owner=None)
        assert isinstance(card, Sorcery)


class TestOverrunResolve:
    """Creatures you control get +3/+3 and trample until EOT."""

    def test_grants_plus_3_plus_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell = Overrun(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.base_power == 5
        assert c1.base_toughness == 5

    def test_grants_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell = Overrun(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE & c1.keywords

    def test_does_not_affect_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        opp = Creature(name="Opp Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp)
        spell = Overrun(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp.base_power == 2
        assert opp.base_toughness == 2

