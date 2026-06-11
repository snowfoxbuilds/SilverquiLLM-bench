"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


class Refrain(Instant):
    """Probe instant {3}{R} with an observable resolution (gain 1 life)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Refrain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert CardType.CREATURE in card.card_types


class TestOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self) -> None:
        """3 creatures → {3}{B}{G} payable."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0,
            battlefield=_bears(3),
            hand=[wb],
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(wb)
        assert game.players[0].mana_pool.total() == 0

    def test_affinity_never_reduces_colored_pips(self) -> None:
        """8 creatures clamps at generic 6 — {B}{G} still required."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0,
            battlefield=_bears(8),
            hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(wb)

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0,
            hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_your_instants_cost_less_per_creature(self) -> None:
        """Witherbloom + 2 bears = 3 creatures → {3}{R} becomes {R}."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        spell = Refrain()
        set_board_state(
            game, 0,
            battlefield=[wb] + _bears(2),
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        cast_spell(game, 0, "Refrain")
        assert game.players[0].life == 21
        assert game.players[0].zones[Zone.GRAVEYARD].contains(spell)

    def test_opponents_spells_unaffected(self) -> None:
        """Witherbloom controls p1's board; p2's instant gets no discount."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        spell = Refrain()
        set_board_state(game, 1, hand=[spell], mana={ManaType.RED: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Refrain")

    def test_creature_spells_not_granted_affinity(self) -> None:
        """The grant is instants/sorceries only — a creature spell pays full."""
        game = create_game()
        wb = WitherbloomTheBalancer()
        bear_card = Creature(
            name="Costly Bear", mana_cost=ManaCost(generic=4),
            base_power=2, base_toughness=2,
        )
        set_board_state(
            game, 0,
            battlefield=[wb] + _bears(2),
            hand=[bear_card],
            mana={ManaType.COLORLESS: 1},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Costly Bear")
