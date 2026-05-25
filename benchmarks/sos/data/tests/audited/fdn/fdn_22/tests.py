"""Audited tests for FDN 22 — Raise the Past."""

from __future__ import annotations

from card_impl import RaiseThePast
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestRaiseThePastBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = RaiseThePast(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = RaiseThePast(owner=None)
        assert card.name == "Raise the Past"

    def test_mana_cost(self) -> None:
        card = RaiseThePast(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{W}")


class TestRaiseThePastResolve:
    """Return all creature cards with MV <= 2 from graveyard to battlefield."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        # MV 1 creature
        c1 = Creature(name="Llanowar Elf", mana_cost=ManaCost.parse("{G}"),
                       base_power=1, base_toughness=1, owner=p1, controller=p1)
        # MV 2 creature
        c2 = Creature(name="Grizzly Bears", mana_cost=ManaCost.parse("{1}{G}"),
                       base_power=2, base_toughness=2, owner=p1, controller=p1)
        # MV 3 creature (should NOT be returned)
        c3 = Creature(name="Centaur Courser", mana_cost=ManaCost.parse("{2}{G}"),
                       base_power=3, base_toughness=3, owner=p1, controller=p1)
        gy = p1.zones[Zone.GRAVEYARD]
        gy.add(c1)
        gy.add(c2)
        gy.add(c3)
        spell = RaiseThePast(owner=p1, controller=p1)
        return game, p1, c1, c2, c3, spell

    def test_returns_mv_1_creature(self) -> None:
        game, p1, c1, c2, c3, spell = self._setup()
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert bf.contains(c1)

    def test_returns_mv_2_creature(self) -> None:
        game, p1, c1, c2, c3, spell = self._setup()
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert bf.contains(c2)

    def test_does_not_return_mv_3_creature(self) -> None:
        game, p1, c1, c2, c3, spell = self._setup()
        spell.on_resolve(game)
        gy = p1.zones[Zone.GRAVEYARD]
        assert gy.contains(c3)

    def test_empty_graveyard_does_not_error(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = RaiseThePast(owner=p1, controller=p1)
        spell.on_resolve(game)  # Should not raise

    def test_non_creature_cards_ignored(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from benchmarks.sos.workspace.engine.card import Instant
        non_creature = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"),
                               owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(non_creature)
        spell = RaiseThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert not bf.contains(non_creature)

    def test_mv_0_creature_returned(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c0 = Creature(name="Memnite", mana_cost=ManaCost.parse("{0}"),
                       base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(c0)
        spell = RaiseThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert game.get_battlefield(p1).contains(c0)
