"""Audited tests for FDN 151 — Aetherize."""

from __future__ import annotations

from card_impl import Aetherize
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestAetherizeBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = Aetherize(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = Aetherize(owner=None)
        assert card.name == "Aetherize"

    def test_mana_cost(self) -> None:
        card = Aetherize(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")


class TestAetherizeResolve:
    """Return all attacking creatures to their owner's hand."""

    def test_returns_attacking_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        attacker = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        attacker.attacking = True
        game.get_battlefield(p1).add(attacker)
        spell = Aetherize(owner=p2, controller=p2)
        spell.on_resolve(game)
        bf_names = [getattr(c, "name", "") for c in game.get_battlefield(p1).get_all()]
        assert "Bear" not in bf_names

    def test_returned_creature_goes_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        attacker = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        attacker.attacking = True
        game.get_battlefield(p1).add(attacker)
        spell = Aetherize(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Bear" in hand_names

    def test_does_not_return_non_attacking(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        creature.attacking = False
        game.get_battlefield(p1).add(creature)
        spell = Aetherize(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert game.get_battlefield(p1).contains(creature)

    def test_returns_multiple_attackers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        a1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        a2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1, controller=p1)
        a1.attacking = True
        a2.attacking = True
        game.get_battlefield(p1).add(a1)
        game.get_battlefield(p1).add(a2)
        spell = Aetherize(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        creatures = [c for c in bf if CardType.CREATURE in getattr(c, "card_types", set())]
        assert len(creatures) == 0

    def test_empty_battlefield_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = Aetherize(owner=p1, controller=p1)
        spell.on_resolve(game)  # Should not raise
