"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError as _CastError
from test_utils import cast_spell, create_game, set_board_state


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class _Filler(Instant):
    """Trivial instant, {3}{R}, no targets/effect — used to probe cost."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Filler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)


class TestProperties:
    def test_static(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")


class TestSelfAffinity:
    def test_three_creatures_reduce_three(self) -> None:
        """3 creatures you control → {6}{B}{G} becomes {3}{B}{G}."""
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=_bears(3))
        set_board_state(
            game, 0, hand=[WitherbloomTheBalancer(owner=None)],
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert any(
            getattr(c, "name", None) == "Witherbloom, the Balancer"
            for c in game.get_battlefield(p0).get_all()
        )

    def test_no_creatures_full_cost(self) -> None:
        """0 creatures → full {6}{B}{G}; {5}{B}{G} is insufficient."""
        game = create_game()
        set_board_state(game, 0, battlefield=[])
        set_board_state(
            game, 0, hand=[WitherbloomTheBalancer(owner=None)],
            mana={ManaType.COLORLESS: 5, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        with pytest.raises(_CastError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_grants_affinity_to_instant(self) -> None:
        """Witherbloom + 2 bears = 3 creatures → instant {3}{R} costs {R}."""
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wb, *_bears(2)])
        set_board_state(game, 0, hand=[_Filler(owner=None)],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Filler")
        assert any(
            getattr(c, "name", None) == "Filler"
            for c in game.get_graveyard(p0).get_all()
        )

    def test_grant_clamped_generic_only(self) -> None:
        """Reduction is generic-only and clamped at 0 — colored pip remains."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p0, controller=p0)
        # 5 creatures total (Witherbloom + 4 bears) but {3}{R} clamps to 3.
        set_board_state(game, 0, battlefield=[wb, *_bears(4)])
        filler = _Filler(owner=p0, controller=p0)
        red = get_cost_reduction(game, filler, p0)
        assert red == 3  # clamped to the generic portion
