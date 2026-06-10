"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestWitherbloom:
    def test_keywords(self):
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_own_affinity_reduces_generic(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(
            game, 0, battlefield=_bears(3), hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        p1 = game.players[0]
        assert game.get_battlefield(p1).contains(wb)
        assert p1.mana_pool.total() == 0

    def test_no_creatures_no_reduction(self):
        game = create_game()
        set_board_state(
            game, 0, hand=[WitherbloomTheBalancer()],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_grants_affinity_to_your_instants(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        # Witherbloom + 2 bears = 3 creatures -> instant {3}{U} costs just {U}.
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, hand=[probe], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert game.players[0].mana_pool.total() == 0

    def test_granted_affinity_never_reduces_colored_pips(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb] + _bears(4))
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{1}{U}"))
        set_board_state(game, 0, hand=[probe], mana={})
        # 5 creatures, but only the {1} generic can be reduced — {U} unpaid.
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Probe")

    def test_opponents_spells_not_reduced(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        probe = Instant(name="Opp Probe", mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 1, hand=[probe], mana={ManaType.BLUE: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Opp Probe")
