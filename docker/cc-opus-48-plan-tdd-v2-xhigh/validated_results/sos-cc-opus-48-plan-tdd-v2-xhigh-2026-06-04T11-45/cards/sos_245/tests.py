"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_pt(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert c.base_power == 5 and c.base_toughness == 5

    def test_keywords(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes


class TestWitherbloomAffinity:
    def test_self_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])
        # Witherbloom is on the stack while being cast — count the 3 creatures.
        assert wb.cost_reduction(game) == 3

    def test_grants_affinity_to_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Witherbloom + 2 bears = 3 creatures you control.
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B")])
        spell = Instant(name="Bolt", mana_cost=ManaCost.parse("{3}{R}"))
        spell.controller = p1
        spell.owner = p1
        assert get_cost_reduction(game, spell, p1) == 3

    def test_does_not_grant_to_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B")])
        creature_spell = Creature(name="Ox", mana_cost=ManaCost.parse("{3}{G}"),
                                  base_power=3, base_toughness=3)
        creature_spell.controller = p1
        creature_spell.owner = p1
        assert get_cost_reduction(game, creature_spell, p1) == 0
