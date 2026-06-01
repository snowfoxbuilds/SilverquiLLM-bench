"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [Creature(name=f"b{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestWitherbloomProperties:
    def test_name_and_stats(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_keywords_and_types(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestWitherbloomSelfAffinity:
    def test_reduction_equals_creature_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=_bears(3), hand=[wb])
        assert get_cost_reduction(game, wb, p1) == 3

    def test_reduction_clamped_to_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=_bears(9), hand=[wb])
        # Generic portion is only {6}; reduction cannot exceed it.
        assert get_cost_reduction(game, wb, p1) == 6


class TestWitherbloomGrantedAffinity:
    def test_instant_gets_affinity_while_witherbloom_present(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        inst = Instant(name="Big Instant", mana_cost=ManaCost.parse("{5}{R}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[inst])
        inst.controller = p1
        # Creatures controlled = Witherbloom + 2 bears = 3.
        assert get_cost_reduction(game, inst, p1) == 3

    def test_no_affinity_when_witherbloom_absent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        inst = Instant(name="Big Instant", mana_cost=ManaCost.parse("{5}{R}"))
        set_board_state(game, 0, battlefield=_bears(2), hand=[inst])
        inst.controller = p1
        assert get_cost_reduction(game, inst, p1) == 0

    def test_creature_spell_does_not_get_granted_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        other = Creature(
            name="Hippo",
            mana_cost=ManaCost.parse("{4}{G}"),
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, battlefield=[wb] + _bears(2), hand=[other])
        other.controller = p1
        # The granted affinity only applies to instants/sorceries; this
        # creature has no self cost-reduction either.
        assert get_cost_reduction(game, other, p1) == 0
