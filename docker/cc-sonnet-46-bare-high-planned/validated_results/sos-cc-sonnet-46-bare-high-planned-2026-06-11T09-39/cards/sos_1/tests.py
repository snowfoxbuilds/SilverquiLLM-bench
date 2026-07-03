"""Tests for sos_1 — The Dawning Archaic."""

from __future__ import annotations

import pytest
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class TestTheDawningArchaicProperties:
    def test_name(self) -> None:
        assert TheDawningArchaic().name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic().mana_cost.generic == 10

    def test_stats(self) -> None:
        card = TheDawningArchaic()
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic().keywords


class TestTheDawningArchaicCostReduction:
    def test_no_graveyard_no_reduction(self) -> None:
        game = create_game()
        p0 = game.players[0]
        card = TheDawningArchaic()
        card.controller = p0
        assert card.cost_reduction(game) == 0

    def test_two_instants_in_gy(self) -> None:
        game = create_game()
        p0 = game.players[0]
        card = TheDawningArchaic()
        inst1 = Instant(name="Bolt1", mana_cost=ManaCost(generic=1))
        inst2 = Instant(name="Bolt2", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, graveyard=[inst1, inst2])
        card.controller = p0
        assert card.cost_reduction(game) == 2

    def test_reduction_used_at_cast_time(self) -> None:
        """With 3 instants in graveyard, a {10} spell costs {7}."""
        game = create_game()
        p0 = game.players[0]
        i1 = Instant(name="I1", mana_cost=ManaCost(generic=1))
        i2 = Instant(name="I2", mana_cost=ManaCost(generic=1))
        i3 = Sorcery(name="S1", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, graveyard=[i1, i2, i3])
        archaic = TheDawningArchaic()
        set_board_state(game, 0, hand=[archaic], mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        # Should succeed with 7 mana when 3 spells in GY
        bf = game.get_battlefield(p0)
        assert bf.contains(archaic)


class TestTheDawningArchaicAttackTrigger:
    def test_cast_from_gy_on_attack(self) -> None:
        """Attack trigger casts instant from graveyard for free, exiling it."""
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic()
        bolt = Instant(name="Bolt", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False
        archaic.register_triggers(game)  # set_board_state bypasses move_to_zone
        set_board_state(game, 0, graveyard=[bolt])

        # Script: p0 chooses bolt from graveyard
        p0._script.append(bolt)

        declare_attackers(game, ["The Dawning Archaic"])
        # Trigger should be on stack; resolve it
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # Bolt should be in exile (not graveyard)
        gy = game.get_graveyard(p0)
        exile = game.get_exile(p0)
        assert not gy.contains(bolt)
        assert exile.contains(bolt)

    def test_empty_graveyard_no_trigger_target(self) -> None:
        """Empty graveyard — trigger fires but does nothing."""
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)
        # No crash — trigger resolved with empty graveyard

    def test_decline_cast_from_gy(self) -> None:
        """Player declines by choosing None."""
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic()
        bolt = Instant(name="Bolt", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        set_board_state(game, 0, graveyard=[bolt])

        # Script: player declines (None)
        p0._script.append(None)

        declare_attackers(game, ["The Dawning Archaic"])
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # Bolt still in graveyard
        gy = game.get_graveyard(p0)
        assert gy.contains(bolt)
