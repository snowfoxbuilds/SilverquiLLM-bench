"""Audited tests for FDN 6 — Claws Out."""

from __future__ import annotations

from card_impl import ClawsOut
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestClawsOutBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = ClawsOut(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ClawsOut(owner=None)
        assert card.name == "Claws Out"

    def test_mana_cost(self) -> None:
        card = ClawsOut(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}{W}")


class TestClawsOutOnResolve:
    """Creatures you control get +2/+2 until end of turn."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Cat", subtypes={"Cat"}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(c1)
        bf.add(c2)
        spell = ClawsOut(owner=p1, controller=p1)
        return game, p1, c1, c2, spell

    def test_creature_gets_plus_2_power(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.modified_power == 4

    def test_creature_gets_plus_2_toughness(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.modified_toughness == 4

    def test_multiple_creatures_buffed(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c2.modified_power == 3
        assert c2.modified_toughness == 3

    def test_opponent_creatures_not_buffed(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        p2 = game.players[1]
        opp = Creature(name="Opp Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp.base_power == 2
        assert opp.base_toughness == 2

    def test_no_creatures_does_not_error(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ClawsOut(owner=p1, controller=p1)
        spell.on_resolve(game)  # Should not raise
