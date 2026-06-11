"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

import pytest

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import TestSetupError as SetupError
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


def _instant(name: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


class TestStatics:
    def test_card_data(self):
        card = TheDawningArchaic()
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords


class TestCostReduction:
    def test_one_less_per_spell_in_graveyard(self):
        game = create_game()
        card = TheDawningArchaic()
        set_board_state(
            game, 0,
            hand=[card],
            graveyard=[_instant(f"I{i}") for i in range(4)],
            mana={ManaType.COLORLESS: 6},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(card)
        assert game.players[0].mana_pool.total() == 0

    def test_reduction_clamps_at_zero(self):
        game = create_game()
        card = TheDawningArchaic()
        set_board_state(
            game, 0,
            hand=[card],
            graveyard=[_instant(f"I{i}") for i in range(12)],
        )
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(card)

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        card = TheDawningArchaic()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 9})
        with pytest.raises(SetupError):
            cast_spell(game, 0, "The Dawning Archaic")


class TestAttackTrigger:
    def _setup_on_battlefield(self, game, graveyard):
        """Cast The Dawning Archaic through the real pipeline (free via clamp)."""
        card = TheDawningArchaic()
        set_board_state(
            game, 0,
            hand=[card],
            graveyard=[_instant(f"Pad{i}") for i in range(10)],
        )
        cast_spell(game, 0, "The Dawning Archaic")
        set_board_state(game, 0, graveyard=graveyard)
        card.summoning_sick = False
        return card

    def test_single_candidate_autocast_then_exiled(self):
        game = create_game()
        p1, p2 = game.players
        spark = _instant("Spark")
        self._setup_on_battlefield(game, [spark])

        declare_attackers(game, ["The Dawning Archaic"])
        # Resolve the attack trigger, then the free-cast spell.
        p1._script.extend(["pass", "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p1.zones[Zone.EXILE].contains(spark)
        assert not p1.zones[Zone.GRAVEYARD].contains(spark)

    def test_free_cast_resolves_with_target(self):
        game = create_game()
        p1, p2 = game.players
        bolt = BurstLightning()
        self._setup_on_battlefield(game, [bolt])

        declare_attackers(game, ["The Dawning Archaic"])
        # p1: pass (trigger), target for the bolt, pass (bolt); p2: passes.
        p1._script.extend(["pass", p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p2.life == 18
        assert p1.zones[Zone.EXILE].contains(bolt)

    def test_decline_with_multiple_candidates(self):
        game = create_game()
        p1, p2 = game.players
        spells = [_instant("A"), _instant("B")]
        self._setup_on_battlefield(game, spells)

        declare_attackers(game, ["The Dawning Archaic"])
        # p1: pass (trigger), None (decline the choose_card prompt).
        p1._script.extend(["pass", None])
        p2._script.extend(["pass"])
        priority_loop(game)

        for s in spells:
            assert p1.zones[Zone.GRAVEYARD].contains(s)
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_empty_graveyard_no_crash(self):
        game = create_game()
        p1, p2 = game.players
        self._setup_on_battlefield(game, [])

        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert len(p1.zones[Zone.EXILE]) == 0
