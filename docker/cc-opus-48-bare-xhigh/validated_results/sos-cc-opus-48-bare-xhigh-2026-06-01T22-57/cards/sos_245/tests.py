"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert c.name == "Witherbloom, the Balancer"
        assert c.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes
        assert c.keywords & Keyword.FLYING
        assert c.keywords & Keyword.DEATHTOUCH


class TestAffinity:
    def test_cost_reduction_counts_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])
        dragon.controller = p1
        # Affinity for creatures: 3 creatures → {3} less.
        assert dragon.cost_reduction(game) == 3

    def test_grant_to_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[dragon, _bear("A"), _bear("B")])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{3}"))
        # 3 creatures on the battlefield (dragon + 2 bears) → {3} less.
        assert dragon.grant_cost_reduction(game, bolt, p1) == 3

    def test_grant_only_for_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[dragon])
        creature_spell = Creature(name="Ogre", base_power=3, base_toughness=3)
        assert dragon.grant_cost_reduction(game, creature_spell, p1) == 0

    def test_grant_only_for_own_controller(self) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[dragon])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{3}"))
        assert dragon.grant_cost_reduction(game, bolt, p2) == 0
