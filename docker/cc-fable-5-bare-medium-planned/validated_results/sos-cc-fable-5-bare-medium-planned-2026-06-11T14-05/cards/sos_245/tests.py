"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import TestSetupError, create_game, set_board_state, cast_spell


def _bears(n):
    return [Creature(name=f"Bear {i}", base_power=2, base_toughness=2) for i in range(n)]


class TestWitherbloomTheBalancer:
    def test_keywords(self):
        kw = WitherbloomTheBalancer().keywords
        assert Keyword.FLYING in kw and Keyword.DEATHTOUCH in kw

    def test_own_affinity_reduces_generic(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=_bears(4), hand=[wb],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1,
                              ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Witherbloom, the Balancer")  # {6}-4 = {2}{B}{G}
        assert game.get_battlefield(game.players[0]).contains(wb)

    def test_no_creatures_no_reduction(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=[], hand=[wb],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1,
                              ManaType.COLORLESS: 2})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_grants_affinity_to_your_instants(self):
        game = create_game()
        spell = Instant(name="Big Trick", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0,
                        battlefield=[WitherbloomTheBalancer()] + _bears(2),
                        hand=[spell], mana={ManaType.BLUE: 1})
        # 3 creatures controlled (Witherbloom + 2 bears) -> generic 3 -> 0.
        cast_spell(game, 0, "Big Trick")
        assert game.players[0].zones[Zone.GRAVEYARD].contains(spell)

    def test_does_not_reduce_opponents_spells(self):
        game = create_game()
        spell = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, battlefield=[WitherbloomTheBalancer()] + _bears(3))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 1, "Opp Trick")

    def test_colored_pips_never_reduced(self):
        game = create_game()
        spell = Instant(name="Pip Trick", mana_cost=ManaCost.parse("{U}{U}"))
        set_board_state(game, 0,
                        battlefield=[WitherbloomTheBalancer()] + _bears(5),
                        hand=[spell], mana={ManaType.BLUE: 1})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Pip Trick")
