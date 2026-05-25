"""Audited tests for FDN 205 — Seismic Rupture."""

from __future__ import annotations

from card_impl import SeismicRupture
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost
from test_utils import create_game


class TestSeismicRuptureBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = SeismicRupture(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = SeismicRupture(owner=None)
        assert card.name == "Seismic Rupture"

    def test_mana_cost(self) -> None:
        card = SeismicRupture(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestSeismicRuptureResolve:
    """Deals 2 damage to each creature without flying."""

    def test_deals_2_damage_to_ground_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        spell = SeismicRupture(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert creature.damage_marked >= 2

    def test_does_not_damage_flying_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        flyer = Creature(name="Bird", base_power=1, base_toughness=1, owner=p1, controller=p1, keywords=Keyword.FLYING)
        game.get_battlefield(p1).add(flyer)
        spell = SeismicRupture(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert getattr(flyer, "damage_taken", 0) == 0

    def test_damages_both_players_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c1 = Creature(name="Bear1", base_power=2, base_toughness=4, owner=p1, controller=p1)
        c2 = Creature(name="Bear2", base_power=2, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p2).add(c2)
        spell = SeismicRupture(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert c1.damage_marked >= 2
        assert c2.damage_marked >= 2
