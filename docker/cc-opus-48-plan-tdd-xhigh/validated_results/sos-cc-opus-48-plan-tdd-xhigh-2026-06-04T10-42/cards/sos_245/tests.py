"""Tests for SOS 245 — Witherbloom, the Balancer (affinity for creatures)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    b = Creature(name=name, base_power=2, base_toughness=2)
    b.card_types = {CardType.CREATURE}
    return b


class _Spark(Instant):
    """Trivial instant with a configurable mana cost."""

    def __init__(self, cost: str = "{3}", **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse(cost))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


class TestWitherbloomProperties:
    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"
        )

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse(
            "{6}{B}{G}"
        )

    def test_pt(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.DEATHTOUCH in c.keywords

    def test_legendary_dragon(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Dragon" in c.subtypes
        assert "Elder" in c.subtypes


class TestWitherbloomSelfAffinity:
    def test_costs_one_less_per_creature(self) -> None:
        # Three creatures → {6}{B}{G} becomes {3}{B}{G}.
        game = create_game()
        p0, _ = game.players
        witherbloom = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(
            game,
            0,
            battlefield=[_bear("B1"), _bear("B2"), _bear("B3")],
            hand=[witherbloom],
            mana={
                ManaType.COLORLESS: 3,
                ManaType.BLACK: 1,
                ManaType.GREEN: 1,
            },
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        # Paid exactly {3}{B}{G}; nothing left over.
        assert p0.mana_pool.total() == 0
        assert game.get_battlefield(p0).contains(witherbloom)

    def test_no_creatures_no_reduction(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        game = create_game()
        p0, _ = game.players
        c.controller = p0
        assert c.cost_reduction(game) == 0


class TestWitherbloomGrantsAffinity:
    def test_instant_gets_affinity(self) -> None:
        # Witherbloom + two bears = 3 creatures → a {3} instant costs {0}.
        game = create_game()
        p0, _ = game.players
        witherbloom = WitherbloomTheBalancer(owner=p0, controller=p0)
        spark = _Spark(cost="{3}", owner=p0, controller=p0)
        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _bear("B1"), _bear("B2")],
            hand=[spark],
            mana={ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Spark")

        # {3} reduced by 3 → {0}; the spare colorless is untouched.
        assert p0.mana_pool.total() == 1
        assert game.get_graveyard(p0).contains(spark)

    def test_opponent_instant_unaffected(self) -> None:
        # Witherbloom on p0's battlefield does not reduce p1's spells.
        game = create_game()
        p0, p1 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[witherbloom, _bear("B1")])
        spark = _Spark(cost="{2}", owner=p1, controller=p1)
        set_board_state(
            game, 1, hand=[spark], battlefield=[_bear("E1")],
            mana={ManaType.COLORLESS: 2},
        )

        cast_spell(game, 1, "Spark")

        # No reduction for p1 → full {2} paid.
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(spark)
