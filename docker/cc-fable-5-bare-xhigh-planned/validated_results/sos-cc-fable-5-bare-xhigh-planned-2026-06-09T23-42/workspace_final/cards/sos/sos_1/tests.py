"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    TestSetupError,
    cast_spell,
    create_game,
    declare_attackers,
    set_board_state,
)


def _instant(name: str = "Filler Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}"))


class TestCostReduction:
    def test_reduced_by_instants_and_sorceries_in_graveyard(self):
        game = create_game()
        archaic = TheDawningArchaic()
        # 3 instants + 1 creature in graveyard -> reduction is 3, not 4.
        set_board_state(
            game, 0, hand=[archaic],
            graveyard=[_instant("A"), _instant("B"), _instant("C"),
                       Creature(name="Dead Bear", base_power=2, base_toughness=2)],
            mana={ManaType.COLORLESS: 7},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        p1 = game.players[0]
        assert game.get_battlefield(p1).contains(archaic)
        assert p1.mana_pool.total() == 0

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        set_board_state(
            game, 0, hand=[TheDawningArchaic()], mana={ManaType.COLORLESS: 7},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_has_reach(self):
        assert Keyword.REACH in TheDawningArchaic().keywords


class TestAttackTrigger:
    def _setup_attack(self, p1_script, p2_script, graveyard):
        game = create_game(scripts=(p1_script, p2_script))
        archaic = TheDawningArchaic()
        # Cast the Archaic for real so its triggers register on entry.
        spells_in_gy = sum(
            1 for c in graveyard if not hasattr(c, "base_power")
        )
        set_board_state(
            game, 0, hand=[archaic], graveyard=graveyard,
            mana={ManaType.COLORLESS: 10 - spells_in_gy},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        archaic.summoning_sick = False
        declare_attackers(game, ["The Dawning Archaic"])
        return game, archaic

    def test_cast_instant_from_graveyard_then_exile(self):
        spell = _instant("Buried Bolt")
        game, _ = self._setup_attack(
            p1_script=["pass", True, spell, "pass"],
            p2_script=["pass", "pass"],
            graveyard=[spell],
        )
        priority_loop(game)
        p1 = game.players[0]
        assert not game.get_graveyard(p1).contains(spell)
        assert game.get_exile(p1).contains(spell)

    def test_may_decline(self):
        spell = _instant("Buried Bolt")
        game, _ = self._setup_attack(
            p1_script=["pass", False],
            p2_script=["pass"],
            graveyard=[spell],
        )
        priority_loop(game)
        p1 = game.players[0]
        assert game.get_graveyard(p1).contains(spell)
        assert game.get_exile(p1).get_all() == []

    def test_empty_graveyard_trigger_does_nothing(self):
        # No yes/no choice is even offered when there is no legal card.
        game, _ = self._setup_attack(
            p1_script=["pass"], p2_script=["pass"], graveyard=[],
        )
        priority_loop(game)
        p1 = game.players[0]
        assert game.get_exile(p1).get_all() == []

    def test_non_spell_cards_not_castable(self):
        # Only a creature card in the graveyard -> trigger has no legal target.
        game, _ = self._setup_attack(
            p1_script=["pass"],
            p2_script=["pass"],
            graveyard=[Creature(name="Dead Bear", base_power=2, base_toughness=2)],
        )
        priority_loop(game)
        p1 = game.players[0]
        assert len(game.get_graveyard(p1)) == 1
        assert game.get_exile(p1).get_all() == []
