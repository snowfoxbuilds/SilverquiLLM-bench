"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, cast_spell, set_board_state


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestWitherbloom:
    def test_keywords(self) -> None:
        w = WitherbloomTheBalancer()
        assert Keyword.FLYING in w.keywords
        assert Keyword.DEATHTOUCH in w.keywords

    def test_own_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=_bears(3), hand=[w],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1,
                              ManaType.COLORLESS: 3})
        # {6}{B}{G} less {3} = {3}{B}{G}
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(w)
        assert p1.mana_pool.total() == 0

    def test_grants_affinity_to_instants(self) -> None:
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        spell = Instant(name="Big Trick", mana_cost=ManaCost(generic=4))
        # Witherbloom + 2 bears = 3 creatures → {4} becomes {1}.
        set_board_state(game, 0, battlefield=[w] + _bears(2), hand=[spell],
                        mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Big Trick")
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(spell)

    def test_grant_is_generic_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        w = WitherbloomTheBalancer()
        spell = Instant(
            name="Colored Trick",
            mana_cost=ManaCost(generic=1, pips={ManaType.BLUE: 1}),
        )
        set_board_state(game, 0, battlefield=[w] + _bears(4), hand=[spell],
                        mana={ManaType.BLUE: 1})
        # 5 creatures, but only the {1} generic can be reduced; {U} remains.
        cast_spell(game, 0, "Colored Trick")
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(spell)

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        w = WitherbloomTheBalancer()
        game2 = create_game()
        w2 = WitherbloomTheBalancer()
        set_board_state(game2, 0, hand=[w2],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1,
                              ManaType.COLORLESS: 6})
        # 0 creatures → full {6}{B}{G} cost is required and is exactly paid.
        cast_spell(game2, 0, "Witherbloom, the Balancer")
        assert game2.players[0].mana_pool.total() == 0
