"""Tests for SOS 245 — Witherbloom, the Balancer (affinity + granting)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class _BigSpell(Instant):
    """Test instant with a high generic cost and no effect."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Big Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        super().__init__(**kwargs)


def _bear(player: Any, name: str = "Bear") -> Creature:
    c = Creature(
        name=name, owner=player, controller=player, base_power=2, base_toughness=2
    )
    c.card_types = {CardType.CREATURE}
    return c


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer().name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer().mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        c = WitherbloomTheBalancer()
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords_and_types(self) -> None:
        c = WitherbloomTheBalancer()
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes


class TestWitherbloomAffinity:
    def test_self_affinity_counts_other_creatures(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_bear(p1), _bear(p1, "Bear2")])
        # Witherbloom is on the stack; 2 creatures controlled → reduce by 2.
        assert get_cost_reduction(game, wither, p1) == 2

    def test_grants_affinity_to_instant(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(p1)])
        spell = _BigSpell(owner=p1, controller=p1)
        # 2 creatures controlled (Witherbloom + Bear) → instant costs {2} less.
        assert get_cost_reduction(game, spell, p1) == 2

    def test_no_affinity_for_noninstant(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(p1)])
        # A vanilla creature spell gains no affinity from Witherbloom.
        creature_spell = Creature(
            name="Ogre", owner=p1, controller=p1, base_power=3, base_toughness=3
        )
        creature_spell.mana_cost = ManaCost.parse("{5}")
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_no_affinity_for_opponent(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(p1)])
        opp_spell = _BigSpell(owner=p2, controller=p2)
        # Witherbloom only helps its own controller's spells.
        assert get_cost_reduction(game, opp_spell, p2) == 0

    def test_instant_castable_with_reduced_mana(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        wither = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _BigSpell(owner=p1, controller=p1)
        # Witherbloom + 3 bears = 4 creatures → {5} instant costs {1}.
        set_board_state(
            game,
            0,
            battlefield=[wither, _bear(p1, "B1"), _bear(p1, "B2"), _bear(p1, "B3")],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Big Spell")
        assert game.get_graveyard(p1).contains(spell)
