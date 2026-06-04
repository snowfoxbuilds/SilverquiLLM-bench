"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse(
            "{6}{B}{G}"
        )

    def test_power_toughness(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert (c.base_power, c.base_toughness) == (5, 5)

    def test_flying_deathtouch_legendary(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestAffinityForCreatures:
    def test_cost_reduction_counts_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear("B1"), _bear("B2")])
        # 3 creatures controlled (Witherbloom + 2 bears).
        assert wither.cost_reduction(game) == 3

    def test_cost_reduction_zero_with_no_board(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Not on the battlefield, no creatures controlled.
        assert wither.cost_reduction(game) == 0


class TestStaticAffinity:
    def test_grants_affinity_to_own_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear("B1")])
        spell = Instant(name="Bolt")
        assert wither.static_cost_reduction(game, spell, p1) == 2

    def test_grants_affinity_to_own_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither])
        spell = Sorcery(name="Ritual")
        assert wither.static_cost_reduction(game, spell, p1) == 1

    def test_no_affinity_for_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear("B1")])
        creature_spell = Creature(name="Beast", base_power=3, base_toughness=3)
        assert wither.static_cost_reduction(game, creature_spell, p1) == 0

    def test_no_affinity_for_opponent_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear("B1")])
        spell = Instant(name="Bolt")
        assert wither.static_cost_reduction(game, spell, p2) == 0
