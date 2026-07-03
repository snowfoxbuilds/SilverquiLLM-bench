"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import TestSetupError, create_game, declare_attackers, set_board_state, cast_spell


def _passes(n: int = 8) -> list:
    return ["pass"] * n


class TestCostReduction:
    def test_costs_one_less_per_instant_sorcery_in_graveyard(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        gy = [
            Instant(name=f"I{i}", mana_cost=ManaCost.parse("{U}"))
            for i in range(3)
        ]
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(archaic)
        assert game.players[0].mana_pool.total() == 0

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, hand=[archaic], mana={ManaType.COLORLESS: 9})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_reduction_clamps_at_zero_generic(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        gy = [
            Sorcery(name=f"S{i}", mana_cost=ManaCost.parse("{R}"))
            for i in range(12)
        ]
        set_board_state(game, 0, hand=[archaic], graveyard=gy, mana={})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(archaic)

    def test_has_reach(self):
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestAttackTrigger:
    def test_attack_casts_graveyard_sorcery_then_exiles_it(self):
        game = create_game(scripts=(_passes(), _passes()))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Sorcery(name="Dull Spell", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        # The single legal card was auto-selected, cast for free, and on
        # resolution exiled instead of returning to the graveyard.
        assert p1.zones[Zone.EXILE].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_attack_with_empty_graveyard_does_nothing(self):
        game = create_game(scripts=(_passes(), _passes()))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[archaic])
        archaic.register_triggers(game)
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert len(p1.zones[Zone.EXILE]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_attack_with_multiple_candidates_may_decline(self):
        # With more than one candidate the controller is prompted and may
        # decline by answering None; both cards stay in the graveyard.
        game = create_game(scripts=([None] + _passes(), _passes()))
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        s1 = Sorcery(name="S1", mana_cost=ManaCost.parse("{R}"))
        s2 = Instant(name="I1", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[s1, s2])
        archaic.register_triggers(game)
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(s1)
        assert p1.zones[Zone.GRAVEYARD].contains(s2)
        assert len(p1.zones[Zone.EXILE]) == 0
