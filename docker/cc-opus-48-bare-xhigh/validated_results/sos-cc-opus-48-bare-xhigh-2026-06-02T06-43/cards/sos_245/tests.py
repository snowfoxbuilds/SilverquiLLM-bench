"""Tests for Witherbloom, the Balancer (SOS 245)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestWitherbloomProperties:
    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert (
            WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"
        )

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.power == 5
        assert card.toughness == 5

    def test_keywords(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_legendary_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Dragon" in card.subtypes
        assert "Elder" in card.subtypes


class TestWitherbloomAffinitySelf:
    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert wither.cost_reduction(game) == 0

    def test_reduction_equals_creature_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert wither.cost_reduction(game) == 3

    def test_get_cost_reduction_clamped_to_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # 8 creatures, but generic is only 6 — reduction clamps to 6.
        set_board_state(game, 0, battlefield=[_bear(f"B{i}") for i in range(8)])
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert get_cost_reduction(game, wither, p1) == 6


class TestWitherbloomStaticGrant:
    def test_instant_gets_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer()
        # Witherbloom plus two bears on the battlefield => 3 creatures.
        set_board_state(game, 0, battlefield=[wither, _bear("A"), _bear("B")])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{4}{R}"))
        assert get_cost_reduction(game, bolt, p1) == 3

    def test_sorcery_gets_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wither, _bear("A")])
        srcy = Sorcery(name="Srcy", mana_cost=ManaCost.parse("{5}"))
        assert get_cost_reduction(game, srcy, p1) == 2

    def test_creature_spell_not_reduced(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wither, _bear("A")])
        beast = Creature(name="Beast", base_power=3, base_toughness=3,
                         mana_cost=ManaCost.parse("{5}"))
        # Witherbloom only grants affinity to instants/sorceries.
        assert get_cost_reduction(game, beast, p1) == 0

    def test_grant_requires_witherbloom_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Witherbloom NOT on the battlefield — no static grant.
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B")])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{4}{R}"))
        assert get_cost_reduction(game, bolt, p1) == 0

    def test_static_hook_direct(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wither = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wither, _bear("A")])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{4}{R}"))
        assert wither.static_cost_reduction(game, bolt, p1) == 2
        # Does not reduce itself.
        assert wither.static_cost_reduction(game, wither, p1) == 0
