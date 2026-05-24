"""Audited tests for FDN 221 — Genesis Wave."""

from __future__ import annotations

from card_impl import GenesisWave
from engine.card import CardImpl, Creature, Enchantment, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestGenesisWaveBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GenesisWave(owner=None)
        assert card.name == "Genesis Wave"

    def test_mana_cost(self) -> None:
        card = GenesisWave(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{G}{G}{G}")

    def test_is_sorcery(self) -> None:
        card = GenesisWave(owner=None)
        assert isinstance(card, Sorcery)


class TestGenesisWaveResolve:
    """Reveals top X, puts permanents with MV <= X onto battlefield."""

    def test_puts_eligible_permanents_onto_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Put creatures with low mana cost in library (top = end)
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1,
                      mana_cost=ManaCost.parse("{1}{G}"))
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1, controller=p1,
                      mana_cost=ManaCost.parse("{2}{G}"))
        library = p1.zones[Zone.LIBRARY]
        library.add(c1)
        library.add(c2)
        wave = GenesisWave(owner=p1, controller=p1)
        wave.x_value = 3
        wave.on_resolve(game)
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Bear" in bf_names
        assert "Elk" in bf_names

    def test_non_permanents_go_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = Instant(name="Bolt", owner=p1, controller=p1, mana_cost=ManaCost.parse("{R}"))
        library = p1.zones[Zone.LIBRARY]
        library.add(spell)
        wave = GenesisWave(owner=p1, controller=p1)
        wave.x_value = 1
        wave.on_resolve(game)
        gy = p1.zones[Zone.GRAVEYARD]
        gy_names = [getattr(c, "name", "") for c in gy.get_all()]
        assert "Bolt" in gy_names

    def test_x_zero_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wave = GenesisWave(owner=p1, controller=p1)
        wave.x_value = 0
        wave.on_resolve(game)
        # Should not error

